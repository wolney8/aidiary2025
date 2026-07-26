import json
import os
import sqlite3
import tempfile
from datetime import date

import pytest
from flask import Flask

from app import create_app
from routes import on_this_day


class _FakePostgresRows:
    def fetchall(self):
        return []


class _FakePostgresConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakePostgresRows()


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            age INTEGER,
            sex TEXT,
            goals TEXT,
            dailydiary_api_key TEXT,
            dreamdiary_api_key TEXT,
            chatgpt_daily_diary_coachname TEXT,
            chatgpt_dream_diary_coachname TEXT
        );
        CREATE TABLE dailydiary_entries (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            entry_date TEXT,
            entry_number INTEGER,
            title TEXT,
            user_message TEXT,
            daily_people_names TEXT,
            daily_places TEXT,
            tags TEXT
        );
        CREATE TABLE dreamdiary_entries (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            entry_date TEXT,
            entry_number INTEGER,
            title TEXT,
            plot TEXT,
            dream_people_names TEXT,
            dream_places TEXT,
            tags TEXT
        );
        """
    )
    conn.close()

    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client, db_path

    os.close(db_fd)
    os.unlink(db_path)


def _register(client, username: str) -> tuple[int, dict[str, str]]:
    response = client.post(
        '/api/register',
        data=json.dumps({'username': username, 'password': 'testpass123'}),
        content_type='application/json',
    )
    payload = json.loads(response.data)
    return payload['user']['id'], {'Authorization': f"Bearer {payload['token']}"}


def test_on_this_day_entry_queries_use_postgres_placeholders():
    app = Flask(__name__)
    app.config['DATABASE_PROVIDER'] = 'postgres'
    conn = _FakePostgresConnection()

    with app.app_context():
        on_this_day._fetch_entry_rows(
            conn,
            user_id=9,
            target=date(2026, 7, 21),
        )

    daily_sql, daily_params = conn.calls[0]
    dream_sql, dream_params = conn.calls[1]
    thought_sql, thought_params = conn.calls[2]
    assert 'entry.user_id = $1' in daily_sql
    assert "to_char((entry.entry_date)::date, 'MM-DD') = $2" in daily_sql
    assert 'EXTRACT(YEAR FROM (entry.entry_date)::date)::integer < $3' in dream_sql
    assert 'worksheet.user_id = $1' in thought_sql
    assert 'EXTRACT(YEAR FROM (worksheet.record_date)::date)::integer < $3' in thought_sql
    assert daily_params == (9, '07-21', 2026, on_this_day.MAX_RESULTS)
    assert dream_params == daily_params
    assert thought_params == daily_params


def test_on_this_day_hide_insert_uses_postgres_conflict_syntax():
    app = Flask(__name__)
    app.config['DATABASE_PROVIDER'] = 'postgres'

    with app.app_context():
        sql = on_this_day._hide_insert_sql()

    assert 'INSERT OR IGNORE' not in sql
    assert 'ON CONFLICT(user_id, entry_type, entry_id) DO NOTHING' in sql
    assert '$1' in sql
    assert '$2' in sql
    assert '$3' in sql


def test_on_this_day_is_opt_in_and_user_scoped(client):
    test_client, db_path = client
    user_id, headers = _register(test_client, 'memory-user')
    other_id, _other_headers = _register(test_client, 'other-user')

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, entry_number, title, user_message, tags) VALUES (?, '2025-07-21', 1, 'A prior day', 'Useful memory', 'growth')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, entry_number, title, user_message, tags) VALUES (?, '2025-07-21', 1, 'Private', 'Other user memory', 'private')",
        (other_id,),
    )
    conn.commit()
    conn.close()

    disabled = test_client.get('/api/on-this-day?date=2026-07-21', headers=headers)
    assert disabled.status_code == 200
    assert json.loads(disabled.data) == {
        'enabled': False,
        'date': '2026-07-21',
        'entries': [],
    }

    update = test_client.put(
        '/api/profile',
        headers=headers,
        data=json.dumps({'show_on_this_day': True}),
        content_type='application/json',
    )
    assert update.status_code == 200

    enabled = test_client.get('/api/on-this-day?date=2026-07-21', headers=headers)
    payload = json.loads(enabled.data)
    assert payload['enabled'] is True
    assert [entry['title'] for entry in payload['entries']] == ['A prior day']


def test_on_this_day_returns_supported_prior_entries_and_excludes_current_year(client):
    test_client, db_path = client
    user_id, headers = _register(test_client, 'mixed-memory-user')
    test_client.put(
        '/api/profile',
        headers=headers,
        data=json.dumps({'show_on_this_day': True}),
        content_type='application/json',
    )

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, entry_number, title, user_message, tags) VALUES (?, '2024-02-29', 1, 'Leap journal', 'Daily memory', 'leap,reflection')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO dreamdiary_entries (user_id, entry_date, entry_number, title, plot, tags) VALUES (?, '2020-02-29', 1, 'Leap dream', 'Dream memory', 'night')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, entry_number, title, user_message, tags) VALUES (?, '2028-02-29', 1, 'Current entry', 'Not a memory yet', '')",
        (user_id,),
    )
    cursor = conn.execute(
        "INSERT INTO cbt_worksheets (user_id, title, status, current_step, record_date) VALUES (?, 'Balanced view', 'completed', 7, '2024-02-29')",
        (user_id,),
    )
    conn.execute(
        "INSERT INTO cbt_thought_record_data (worksheet_id, situation, balanced_thought) VALUES (?, 'A difficult moment', 'I handled it with care')",
        (cursor.lastrowid,),
    )
    conn.commit()
    conn.close()

    response = test_client.get('/api/on-this-day?date=2028-02-29', headers=headers)
    assert response.status_code == 200
    entries = json.loads(response.data)['entries']
    assert {entry['type'] for entry in entries} == {'daily', 'dream', 'thought_record'}
    assert 'Current entry' not in {entry['title'] for entry in entries}
    assert all(entry['entry_date'] < '2028-01-01' for entry in entries)


def test_hiding_memory_is_owned_and_removes_it_from_feed(client):
    test_client, db_path = client
    user_id, headers = _register(test_client, 'hide-user')
    _other_id, other_headers = _register(test_client, 'hide-other')
    test_client.put(
        '/api/profile',
        headers=headers,
        data=json.dumps({'show_on_this_day': True}),
        content_type='application/json',
    )
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, entry_number, title, user_message, tags) VALUES (?, '2025-07-21', 1, 'Hide me', 'Memory', '')",
        (user_id,),
    )
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()

    forbidden = test_client.post(
        '/api/on-this-day/hide',
        headers=other_headers,
        json={'entry_type': 'daily', 'entry_id': entry_id},
    )
    assert forbidden.status_code == 404

    hidden = test_client.post(
        '/api/on-this-day/hide',
        headers=headers,
        json={'entry_type': 'daily', 'entry_id': entry_id},
    )
    assert hidden.status_code == 200

    feed = test_client.get('/api/on-this-day?date=2026-07-21', headers=headers)
    assert json.loads(feed.data)['entries'] == []


def test_on_this_day_rejects_invalid_date(client):
    test_client, _db_path = client
    _user_id, headers = _register(test_client, 'invalid-date-user')
    response = test_client.get('/api/on-this-day?date=21-07-2026', headers=headers)
    assert response.status_code == 400


def test_month_feed_returns_prior_entries_across_selected_month(client):
    test_client, db_path = client
    user_id, headers = _register(test_client, 'month-memory-user')
    test_client.put(
        '/api/profile',
        headers=headers,
        json={'show_on_this_day': True},
    )
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO dailydiary_entries (user_id, entry_date, entry_number, title, user_message, tags) VALUES (?, ?, 1, ?, 'Memory', '')",
        [
            (user_id, '2024-07-03', 'Early July'),
            (user_id, '2025-07-29', 'Late July'),
            (user_id, '2025-08-01', 'Wrong month'),
            (user_id, '2026-07-10', 'Current year'),
        ],
    )
    conn.commit()
    conn.close()

    response = test_client.get('/api/on-this-day?month=2026-07', headers=headers)
    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload['date'] == '2026-07-01'
    assert [entry['title'] for entry in payload['entries']] == [
        'Late July',
        'Early July',
    ]


def test_month_feed_rejects_invalid_month(client):
    test_client, _db_path = client
    _user_id, headers = _register(test_client, 'invalid-month-user')
    response = test_client.get('/api/on-this-day?month=July-2026', headers=headers)
    assert response.status_code == 400

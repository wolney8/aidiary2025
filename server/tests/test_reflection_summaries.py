import json
import os
import sqlite3
import tempfile
from datetime import date
from unittest.mock import patch

import pytest
from flask import Flask

from app import create_app
from routes import reflection_summaries


class _FakePostgresRows:
    def fetchall(self):
        return []


class _FakePostgresConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakePostgresRows()


class _FakeReflectionAdapter:
    def table_columns(self, _conn, table_name):
        if table_name == 'dailydiary_entries':
            return {
                'id',
                'entry_date',
                'title',
                'user_message',
                'mood',
                'tags',
                'daily_people_names',
                'daily_places',
                'ai_response',
            }
        if table_name == 'dreamdiary_entries':
            return {
                'id',
                'entry_date',
                'title',
                'plot',
                'tags',
                'summary',
                'interpretation',
            }
        return set()


@pytest.fixture
def summaries_client():
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'

    conn = sqlite3.connect(db_path)
    conn.execute(
        '''
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
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE dailydiary_entries (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            entry_date TEXT,
            title TEXT,
            user_message TEXT,
            mood TEXT,
            tags TEXT,
            daily_people_names TEXT,
            daily_places TEXT,
            ai_response TEXT
        )
        '''
    )
    conn.execute(
        '''
        CREATE TABLE dreamdiary_entries (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            entry_date TEXT,
            title TEXT,
            plot TEXT,
            tags TEXT,
            summary TEXT,
            interpretation TEXT
        )
        '''
    )
    conn.commit()
    conn.close()

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client, db_path

    os.close(db_fd)
    os.unlink(db_path)


def _register(client, username: str) -> tuple[str, int]:
    response = client.post(
        '/api/register',
        data=json.dumps({'username': username, 'password': 'testpass123'}),
        content_type='application/json',
    )
    payload = json.loads(response.data)
    return payload['token'], payload['user']['id']


def _headers(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def test_runtime_migration_creates_reflection_summaries_table(summaries_client):
    _client, db_path = summaries_client
    conn = sqlite3.connect(db_path)
    columns = {
        row[1]
        for row in conn.execute('PRAGMA table_info(reflection_summaries)').fetchall()
    }
    conn.close()

    assert {'period_type', 'period_start', 'summary_text', 'source_refs_json'} <= columns


def test_reflection_summary_source_queries_use_postgres_placeholders():
    app = Flask(__name__)
    app.config['DATABASE_PROVIDER'] = 'postgres'
    app.config['DATABASE_ADAPTER'] = _FakeReflectionAdapter()
    conn = _FakePostgresConnection()

    with app.app_context():
        reflection_summaries._load_period_sources(
            conn,
            user_id=7,
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
        )

    daily_sql, daily_params = conn.calls[0]
    dream_sql, dream_params = conn.calls[1]
    thought_sql, thought_params = conn.calls[2]
    assert 'WHERE user_id = %s AND (entry_date)::date BETWEEN %s AND %s' in daily_sql
    assert 'WHERE user_id = %s AND (entry_date)::date BETWEEN %s AND %s' in dream_sql
    assert 'WHERE w.user_id = %s AND (w.record_date)::date BETWEEN %s AND %s' in thought_sql
    assert daily_params == (7, '2026-07-01', '2026-07-31')
    assert dream_params == daily_params
    assert thought_params == daily_params


@patch('routes.reflection_summaries.OpenAIService')
def test_generate_list_and_delete_monthly_summary(mock_service_cls, summaries_client):
    client, db_path = summaries_client
    token, user_id = _register(client, 'summary-user')
    mock_service_cls.return_value.generate_reflection_summary.return_value = {
        'title': 'A steadier month',
        'summary_text': 'You had a clearer month with repeated work and therapy themes.',
        'themes': ['work', 'therapy'],
    }

    conn = sqlite3.connect(db_path)
    conn.execute(
        '''
        INSERT INTO dailydiary_entries (
            user_id, entry_date, title, user_message, mood, tags, daily_people_names, daily_places, ai_response
        ) VALUES (?, '2026-07-04', 'Hard meeting', 'A hard meeting happened.', 'anxious', 'work', 'Penny', 'Office', 'You handled it.')
        ''',
        (user_id,),
    )
    conn.commit()
    conn.close()

    response = client.post(
        '/api/reflection-summaries/generate',
        headers=_headers(token),
        json={'period_type': 'monthly', 'period_start': '2026-07-22'},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['period_start'] == '2026-07-01'
    assert payload['title'] == 'A steadier month'
    assert payload['themes'] == ['work', 'therapy']
    assert payload['source_refs'][0]['type'] == 'daily'
    assert mock_service_cls.return_value.generate_reflection_summary.called

    list_response = client.get('/api/reflection-summaries', headers=_headers(token))
    assert list_response.status_code == 200
    listed = list_response.get_json()
    assert len(listed) == 1
    assert listed[0]['id'] == payload['id']

    delete_response = client.delete(
        f"/api/reflection-summaries/{payload['id']}",
        headers=_headers(token),
    )
    assert delete_response.status_code == 200
    assert client.get('/api/reflection-summaries', headers=_headers(token)).get_json() == []


@patch('routes.reflection_summaries.OpenAIService')
def test_generate_summary_includes_thought_record_sources(mock_service_cls, summaries_client):
    client, db_path = summaries_client
    token, user_id = _register(client, 'thought-summary-user')
    mock_service_cls.return_value.generate_reflection_summary.return_value = {
        'title': 'A balanced month',
        'summary_text': 'You used thought records to reframe a difficult situation.',
        'themes': ['thought records'],
    }

    conn = sqlite3.connect(db_path)
    conn.execute(
        '''
        INSERT INTO cbt_worksheets (
            id, user_id, worksheet_type, title, status, current_step, record_date
        ) VALUES (10, ?, 'thought_record', 'Work worry', 'completed', 7, '2026-07-12')
        ''',
        (user_id,),
    )
    conn.execute(
        '''
        INSERT INTO cbt_thought_record_data (
            worksheet_id, situation, balanced_thought, next_step, ai_response
        ) VALUES (
            10,
            'A work message felt sharp.',
            'There may be another explanation and I can check calmly.',
            'Reply after lunch.',
            'This is a useful reframe.'
        )
        '''
    )
    conn.commit()
    conn.close()

    response = client.post(
        '/api/reflection-summaries/generate',
        headers=_headers(token),
        json={'period_type': 'monthly', 'period_start': '2026-07-01'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['source_refs'] == [
        {'type': 'thought_record', 'id': 10, 'date': '2026-07-12', 'theme': 'Work worry'}
    ]
    source_context = mock_service_cls.return_value.generate_reflection_summary.call_args.args[2]
    assert 'Thought record on Sunday, 12 July 2026: Work worry' in source_context
    assert 'There may be another explanation' in source_context


@patch('routes.reflection_summaries.OpenAIService')
def test_empty_period_returns_clear_summary_without_ai_call(mock_service_cls, summaries_client):
    client, _db_path = summaries_client
    token, _user_id = _register(client, 'empty-summary-user')

    response = client.post(
        '/api/reflection-summaries/generate',
        headers=_headers(token),
        json={'period_type': 'weekly', 'period_start': '2026-07-22'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['period_start'] == '2026-07-20'
    assert payload['source_refs'] == []
    assert 'nothing reliable to summarise' in payload['summary_text']
    mock_service_cls.return_value.generate_reflection_summary.assert_not_called()

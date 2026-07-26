import json
import os
import sqlite3
import tempfile
from datetime import date
from unittest.mock import patch

import pytest
from flask import Flask

from app import create_app
from routes import cbt


class _FakePostgresRows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _FakePostgresConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakePostgresRows([{'entry_date': '2026-07-21'}])


@pytest.fixture
def cbt_client():
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
            entry TEXT,
            image_storage_key TEXT
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
            plot TEXT
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


def test_cbt_helpers_support_postgres_placeholders_and_returning_id():
    app = Flask(__name__)
    app.config['DATABASE_PROVIDER'] = 'postgres'
    conn = _FakePostgresConnection()

    with app.app_context():
        linked_type, linked_id, linked_entry_date = cbt._validate_link(
            conn,
            user_id=3,
            entry_type='daily',
            entry_id=12,
        )
        worksheet_sql = cbt._sql(cbt._worksheet_query('w.id = ? AND w.user_id = ?'))
        insert_sql = cbt._sql(
            cbt.append_returning_id(
                '''
                INSERT INTO cbt_worksheets (
                    user_id, worksheet_type, title, status, current_step,
                    record_date, linked_entry_type, linked_entry_id
                ) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
                ''',
                cbt._database_provider(),
            )
        )

    link_sql, link_params = conn.calls[0]
    assert linked_type == 'daily'
    assert linked_id == 12
    assert linked_entry_date == '2026-07-21'
    assert 'FROM dailydiary_entries WHERE id = $1 AND user_id = $2' in link_sql
    assert link_params == (12, 3)
    assert 'WHERE w.id = $1 AND w.user_id = $2' in worksheet_sql
    assert "VALUES ($1, $2, $3, 'draft', $4, $5, $6, $7)" in insert_sql
    assert 'RETURNING id' in insert_sql


def _complete_payload() -> dict[str, object]:
    return {
        'title': 'Difficult meeting',
        'current_step': 7,
        'situation': 'A meeting ended without a decision.',
        'feelings_before': [{'label': 'Anxious', 'intensity': 80}],
        'unhelpful_thoughts': 'I will be blamed for the delay.',
        'evidence_for': 'The deadline is close.',
        'evidence_against': 'The whole team owns the decision.',
        'balanced_thought': 'I can clarify the next action without taking all the blame.',
        'feelings_after': [{'label': 'Anxious', 'intensity': 45}],
        'next_step': 'Send a concise list of decisions needed.',
    }


def test_runtime_migration_creates_cbt_tables(cbt_client):
    _client, db_path = cbt_client
    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    worksheet_columns = {
        row[1]
        for row in conn.execute('PRAGMA table_info(cbt_worksheets)').fetchall()
    }
    data_columns = {
        row[1]
        for row in conn.execute('PRAGMA table_info(cbt_thought_record_data)').fetchall()
    }
    conn.close()

    assert {'cbt_worksheets', 'cbt_thought_record_data'} <= tables
    assert 'record_date' in worksheet_columns
    assert {'ai_response', 'ai_responded_at', 'ai_response_outdated'} <= data_columns


def test_create_save_resume_and_complete_thought_record(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-flow')

    created_response = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'title': 'Meeting reflection'},
    )
    assert created_response.status_code == 201
    created = created_response.get_json()
    assert created['status'] == 'draft'
    assert created['current_step'] == 1
    assert created['record_date'] == date.today().isoformat()

    update_response = client.put(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token),
        json=_complete_payload(),
    )
    assert update_response.status_code == 200
    updated = update_response.get_json()
    assert updated['balanced_thought'].startswith('I can clarify')
    assert updated['before_peak_intensity'] == 80
    assert updated['after_peak_intensity'] == 45
    assert updated['intensity_change'] == -35

    resumed_response = client.get(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token),
    )
    assert resumed_response.status_code == 200
    assert resumed_response.get_json()['next_step'].startswith('Send a concise')

    complete_response = client.post(
        f"/api/cbt/worksheets/{created['id']}/complete",
        headers=_headers(token),
    )
    assert complete_response.status_code == 200
    completed = complete_response.get_json()
    assert completed['status'] == 'completed'
    assert completed['completed_at']


def test_worksheets_are_user_scoped(cbt_client):
    client, _db_path = cbt_client
    token_one, _user_one = _register(client, 'cbt-owner')
    token_two, _user_two = _register(client, 'cbt-other')

    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token_one),
        json={'title': 'Private reflection'},
    ).get_json()

    forbidden_read = client.get(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token_two),
    )
    forbidden_update = client.put(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token_two),
        json={'title': 'Changed'},
    )
    assert forbidden_read.status_code == 404
    assert forbidden_update.status_code == 404
    assert client.get('/api/cbt/worksheets', headers=_headers(token_two)).get_json() == []


def test_completion_requires_all_seven_steps(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-validation')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'situation': 'A difficult moment'},
    ).get_json()

    response = client.post(
        f"/api/cbt/worksheets/{created['id']}/complete",
        headers=_headers(token),
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Complete all seven reflection steps before finishing'


def test_feeling_ratings_are_validated(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-ratings')

    response = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'feelings_before': [{'label': 'Worried', 'intensity': 101}]},
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == 'Feeling intensity must be between 0 and 100'


def test_linked_entry_must_belong_to_current_user(cbt_client):
    client, db_path = cbt_client
    token_one, user_one = _register(client, 'cbt-link-owner')
    token_two, user_two = _register(client, 'cbt-link-other')
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, title, entry) VALUES (?, '2026-07-21', 'Entry', 'Text')",
        (user_one,),
    )
    entry_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()

    linked = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token_one),
        json={'linked_entry_type': 'daily', 'linked_entry_id': entry_id},
    )
    rejected = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token_two),
        json={'linked_entry_type': 'daily', 'linked_entry_id': entry_id},
    )
    assert linked.status_code == 201
    assert linked.get_json()['linked_entry_id'] == entry_id
    assert linked.get_json()['record_date'] == '2026-07-21'
    assert rejected.status_code == 400
    assert rejected.get_json()['error'] == 'Linked entry was not found'
    assert user_two != user_one


def test_thought_record_date_can_be_set_and_updated(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-record-date')

    created_response = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'title': 'Earlier reflection', 'record_date': '2026-06-14'},
    )
    assert created_response.status_code == 201
    created = created_response.get_json()
    assert created['record_date'] == '2026-06-14'

    updated_response = client.put(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token),
        json={'record_date': '2026-06-15'},
    )
    assert updated_response.status_code == 200
    assert updated_response.get_json()['record_date'] == '2026-06-15'


def test_thought_record_date_rejects_invalid_values(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-invalid-record-date')

    response = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'record_date': '21/07/2026'},
    )

    assert response.status_code == 400
    assert response.get_json()['error'] == 'Thought record date must be a valid date'


def test_delete_removes_thought_record_data(cbt_client):
    client, db_path = cbt_client
    token, _user_id = _register(client, 'cbt-delete')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'title': 'Delete me'},
    ).get_json()

    response = client.delete(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token),
    )
    assert response.status_code == 200

    conn = sqlite3.connect(db_path)
    data_row = conn.execute(
        'SELECT 1 FROM cbt_thought_record_data WHERE worksheet_id = ?',
        (created['id'],),
    ).fetchone()
    conn.close()
    assert data_row is None


def test_completed_thought_record_is_read_only_but_can_be_revised(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-completed-read-only')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json=_complete_payload(),
    ).get_json()
    completed = client.post(
        f"/api/cbt/worksheets/{created['id']}/complete",
        headers=_headers(token),
    )
    assert completed.status_code == 200

    response = client.put(
        f"/api/cbt/worksheets/{created['id']}",
        headers=_headers(token),
        json={'title': 'Changed after completion'},
    )
    assert response.status_code == 409
    assert response.get_json()['error'] == 'Completed worksheets are read-only'

    revised = client.put(
        f"/api/cbt/worksheets/{created['id']}/revise",
        headers=_headers(token),
        json={**_complete_payload(), 'title': 'Changed after completion'},
    )
    assert revised.status_code == 200
    assert revised.get_json()['status'] == 'completed'
    assert revised.get_json()['completed_at'] == completed.get_json()['completed_at']
    assert revised.get_json()['title'] == 'Changed after completion'

    drafts = client.get(
        '/api/cbt/worksheets?status=draft',
        headers=_headers(token),
    ).get_json()
    assert all(item['id'] != created['id'] for item in drafts)


@patch('routes.cbt.OpenAIService')
def test_completed_thought_record_can_store_ai_response(mock_service_cls, cbt_client):
    client, db_path = cbt_client
    token, _user_id = _register(client, 'cbt-ai-response')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json=_complete_payload(),
    ).get_json()
    client.post(
        f"/api/cbt/worksheets/{created['id']}/complete",
        headers=_headers(token),
    )
    mock_service_cls.return_value.analyse_thought_record.return_value = (
        'You tested the thought against the evidence and found a more balanced view.'
    )

    response = client.post(
        f"/api/cbt/worksheets/{created['id']}/analyse",
        headers=_headers(token),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ai_response'].startswith('You tested the thought')
    assert payload['ai_responded_at']
    assert payload['ai_response_outdated'] is False
    assert 'Situation: A meeting ended' in (
        mock_service_cls.return_value.analyse_thought_record.call_args.args[0]
    )

    conn = sqlite3.connect(db_path)
    stored = conn.execute(
        'SELECT ai_response FROM cbt_thought_record_data WHERE worksheet_id = ?',
        (created['id'],),
    ).fetchone()[0]
    conn.close()
    assert stored == payload['ai_response']


@patch('routes.cbt.OpenAIService')
def test_edit_marks_ai_response_outdated_until_regenerated(mock_service_cls, cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-outdated-ai-response')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json=_complete_payload(),
    ).get_json()
    client.post(
        f"/api/cbt/worksheets/{created['id']}/complete",
        headers=_headers(token),
    )
    mock_service_cls.return_value.analyse_thought_record.return_value = 'Initial response'
    initial = client.post(
        f"/api/cbt/worksheets/{created['id']}/analyse",
        headers=_headers(token),
    ).get_json()
    assert initial['ai_response_outdated'] is False

    revised = client.put(
        f"/api/cbt/worksheets/{created['id']}/revise",
        headers=_headers(token),
        json={**_complete_payload(), 'balanced_thought': 'A revised balanced thought.'},
    ).get_json()
    assert revised['ai_response_outdated'] is True

    mock_service_cls.return_value.analyse_thought_record.return_value = 'Updated response'
    refreshed = client.post(
        f"/api/cbt/worksheets/{created['id']}/analyse",
        headers=_headers(token),
    ).get_json()
    assert refreshed['ai_response_outdated'] is False


@patch('routes.cbt.OpenAIService')
def test_draft_thought_record_can_store_ai_response(mock_service_cls, cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-draft-ai-response')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={
            'situation': 'I received difficult feedback during a team meeting.',
            'unhelpful_thoughts': 'I assumed everyone thought I was incapable.',
        },
    ).get_json()
    mock_service_cls.return_value.analyse_thought_record.return_value = (
        'You have identified an assumption that can be tested against the evidence.'
    )

    response = client.post(
        f"/api/cbt/worksheets/{created['id']}/analyse",
        headers=_headers(token),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['status'] == 'draft'
    assert payload['ai_response'].startswith('You have identified')


def test_sparse_draft_rejects_ai_response(cbt_client):
    client, _db_path = cbt_client
    token, _user_id = _register(client, 'cbt-sparse-ai-response')
    created = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'situation': 'Too short'},
    ).get_json()

    response = client.post(
        f"/api/cbt/worksheets/{created['id']}/analyse",
        headers=_headers(token),
    )

    assert response.status_code == 400
    assert response.get_json()['error'].startswith('Add more detail')


def test_deleting_linked_entry_preserves_and_unlinks_thought_record(cbt_client):
    client, db_path = cbt_client
    token, user_id = _register(client, 'cbt-entry-delete')
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
        "INSERT INTO dailydiary_entries (user_id, entry_date, title, entry) VALUES (?, '2026-07-21', 'Entry', 'Text')",
        (user_id,),
    )
    entry_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()

    worksheet = client.post(
        '/api/cbt/worksheets',
        headers=_headers(token),
        json={'linked_entry_type': 'daily', 'linked_entry_id': entry_id},
    ).get_json()
    response = client.delete(
        f'/api/daily/{entry_id}',
        headers=_headers(token),
    )
    assert response.status_code == 204

    preserved = client.get(
        f"/api/cbt/worksheets/{worksheet['id']}",
        headers=_headers(token),
    ).get_json()
    assert preserved['linked_entry_type'] is None
    assert preserved['linked_entry_id'] is None

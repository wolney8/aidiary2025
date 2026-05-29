import json
import os
import tempfile
from uuid import uuid4

import pytest

from app import create_app


@pytest.fixture
def client():
    """Create test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        import sqlite3

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
            CREATE TABLE chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            '''
        )
        conn.commit()
        conn.close()

        yield client

    os.close(db_fd)
    os.unlink(db_path)


def _register_and_get_token(client, username: str) -> str:
    response = client.post(
        '/api/register',
        data=json.dumps({'username': username, 'password': 'testpass123'}),
        content_type='application/json',
    )
    data = json.loads(response.data)
    return data['token']


def test_chat_endpoints_require_auth(client):
    conversation_id = str(uuid4())

    post_response = client.post(
        '/api/chat/message',
        data=json.dumps({'conversation_id': conversation_id, 'message': 'Hello'}),
        content_type='application/json',
    )
    get_response = client.get(f'/api/chat/history?conversation_id={conversation_id}')
    delete_response = client.delete(f'/api/chat/conversation?conversation_id={conversation_id}')

    assert post_response.status_code == 401
    assert get_response.status_code == 401
    assert delete_response.status_code == 401


def test_chat_validation_errors(client):
    token = _register_and_get_token(client, 'chat_validation_user')

    invalid_uuid_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': 'not-a-uuid', 'message': 'Hello'}),
        content_type='application/json',
    )
    assert invalid_uuid_response.status_code == 400

    empty_message_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': str(uuid4()), 'message': '   '}),
        content_type='application/json',
    )
    assert empty_message_response.status_code == 400

    too_long_message_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': str(uuid4()), 'message': 'a' * 2001}),
        content_type='application/json',
    )
    assert too_long_message_response.status_code == 400


def test_chat_send_history_clear_flow(client):
    token = _register_and_get_token(client, 'chat_flow_user')
    conversation_id = str(uuid4())

    send_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': conversation_id, 'message': 'How am I doing?'}),
        content_type='application/json',
    )

    assert send_response.status_code == 200
    send_data = json.loads(send_response.data)
    assert send_data['conversation_id'] == conversation_id
    assert 'assistant_reply' in send_data

    history_response = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert history_response.status_code == 200

    history_data = json.loads(history_response.data)
    assert history_data['conversation_id'] == conversation_id
    assert len(history_data['messages']) == 2
    assert history_data['messages'][0]['role'] == 'user'
    assert history_data['messages'][0]['message'] == 'How am I doing?'
    assert history_data['messages'][1]['role'] == 'assistant'

    clear_response = client.delete(
        f'/api/chat/conversation?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert clear_response.status_code == 200

    history_after_clear = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert history_after_clear.status_code == 200

    cleared_data = json.loads(history_after_clear.data)
    assert cleared_data['messages'] == []


def test_chat_user_isolation_by_token(client):
    token_a = _register_and_get_token(client, 'chat_user_a')
    token_b = _register_and_get_token(client, 'chat_user_b')
    conversation_id = str(uuid4())

    send_a = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token_a}'},
        data=json.dumps({'conversation_id': conversation_id, 'message': 'User A secret'}),
        content_type='application/json',
    )
    assert send_a.status_code == 200

    history_b = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token_b}'},
    )
    assert history_b.status_code == 200
    data_b = json.loads(history_b.data)
    assert data_b['messages'] == []

    history_a = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token_a}'},
    )
    assert history_a.status_code == 200
    data_a = json.loads(history_a.data)
    assert len(data_a['messages']) == 2
    assert data_a['messages'][0]['message'] == 'User A secret'


def test_chat_returns_503_when_storage_not_initialised(client):
    token = _register_and_get_token(client, 'chat_missing_table_user')
    conversation_id = str(uuid4())

    db_path = client.application.config['DATABASE_PATH']

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute('DROP TABLE chat_messages')
    conn.commit()
    conn.close()

    send_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': conversation_id, 'message': 'Hello'}),
        content_type='application/json',
    )

    assert send_response.status_code == 503
    data = json.loads(send_response.data)
    assert data['error'] == 'chat storage not initialised'
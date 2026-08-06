import json
import os
import tempfile
from unittest.mock import patch
from uuid import uuid4

import pytest
from flask import Flask

from app import create_app
from extensions import limiter
from routes.chat import _load_model_history, _load_request_messages, _persist_message
from services.chat_observability import ChatObservabilityService
from services.openai_svc import ChatStreamError


@pytest.fixture
def client():
    """Create test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'

    app = create_app()
    app.config['TESTING'] = True
    app.config['RATELIMIT_ENABLED'] = False

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
        conn.commit()
        conn.close()

        yield client

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(autouse=True)
def mocked_chat_services():
    with (
        patch('routes.chat.ChatContextService') as context_service,
        patch('routes.chat.OpenAIService') as openai_service,
    ):
        context_service.return_value.build_system_prompt.return_value = 'System context'
        openai_service.return_value.chat_companion.return_value = iter(['Helpful ', 'reply'])
        yield context_service, openai_service


def _sse_events(response) -> list[dict]:
    events = []
    for block in response.get_data(as_text=True).strip().split('\n\n'):
        assert block.startswith('data: ')
        events.append(json.loads(block.removeprefix('data: ')))
    return events


def _register_and_get_token(client, username: str) -> str:
    response = client.post(
        '/api/register',
        data=json.dumps({'username': username, 'password': 'testpass123'}),
        content_type='application/json',
    )
    data = json.loads(response.data)
    return data['token']


class _FakePostgresConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return []


class _FakeAdapter:
    provider = 'postgres'

    def __init__(self):
        self.connection = _FakePostgresConnection()

    def connect(self, **_kwargs):
        adapter = self

        class _Context:
            def __enter__(self):
                return adapter.connection

            def __exit__(self, exc_type, exc, traceback):
                return False

        return _Context()


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


def test_chat_observability_uses_adapter_placeholders_for_postgres():
    adapter = _FakeAdapter()
    service = ChatObservabilityService('/unused/sqlite.db', adapter=adapter)

    service.record_event(event_type='completed', user_id=1, input_tokens=2)
    service.build_report(user_id=1)

    insert_sql = adapter.connection.calls[0][0]
    report_sql = adapter.connection.calls[1][0]
    assert insert_sql.count('%s') == 10
    assert report_sql.count('%s') == 2


def test_chat_storage_helpers_use_postgres_placeholders():
    app = Flask(__name__)
    app.config['DATABASE_PROVIDER'] = 'postgres'
    conn = _FakePostgresConnection()

    with app.app_context():
        _persist_message(
            conn,
            user_id=1,
            conversation_id=str(uuid4()),
            role='user',
            content='Hello',
            request_id=str(uuid4()),
        )
        _load_request_messages(conn, 1, str(uuid4()))
        _load_model_history(conn, 1, str(uuid4()))

    insert_sql = conn.calls[0][0]
    request_sql = conn.calls[1][0]
    history_sql = conn.calls[2][0]
    assert insert_sql.count('%s') == 6
    assert request_sql.count('%s') == 2
    assert history_sql.count('%s') == 3


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


def test_chat_send_history_clear_flow(client, mocked_chat_services):
    token = _register_and_get_token(client, 'chat_flow_user')
    conversation_id = str(uuid4())

    send_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': conversation_id, 'message': 'How am I doing?'}),
        content_type='application/json',
    )

    assert send_response.status_code == 200
    assert send_response.mimetype == 'text/event-stream'
    events = _sse_events(send_response)
    assert events == [
        {'chunk': '', 'done': False, 'event': 'started', 'retry_after_ms': 1000},
        {'chunk': 'Helpful ', 'done': False},
        {'chunk': 'reply', 'done': False},
        {'chunk': '', 'done': True, 'token_count': 4},
    ]

    context_service, openai_service = mocked_chat_services
    context_service.return_value.build_system_prompt.assert_called_once_with(1)
    call_kwargs = openai_service.return_value.chat_companion.call_args.kwargs
    assert call_kwargs['system_prompt'] == 'System context'
    assert call_kwargs['messages'][-1] == {
        'role': 'user',
        'content': 'How am I doing?',
    }

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
    assert history_data['messages'][1]['message'] == 'Helpful reply'

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

    report_response = client.get(
        '/api/chat/observability/report?days=7',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert report_response.status_code == 200
    report = json.loads(report_response.data)
    assert report['event_counts']['request_started'] == 1
    assert report['event_counts']['completed'] == 1
    assert report['completed_events'] == 1
    assert report['failed_events'] == 0
    assert report['success_completion_rate'] == 1
    assert report['slo_summary']['status'] == 'met'
    assert report['slo_status']['success_completion_rate']['met'] is True
    assert report['slo_status']['error_rate']['met'] is True
    assert report['slo_status']['p95_latency_ms']['met'] is True
    assert report['slo_status']['rate_limit_events']['met'] is True
    assert report['slo_alerts'] == []
    assert report['token_usage']['input_tokens'] > 0
    assert report['token_usage']['output_tokens'] > 0


def test_chat_retry_reuses_request_without_duplicate_messages(client, mocked_chat_services):
    token = _register_and_get_token(client, 'chat_retry_user')
    conversation_id = str(uuid4())
    request_id = str(uuid4())
    _, openai_service = mocked_chat_services

    def failed_stream():
        raise ChatStreamError('provider unavailable')
        yield

    openai_service.return_value.chat_companion.return_value = failed_stream()
    payload = {
        'conversation_id': conversation_id,
        'request_id': request_id,
        'message': 'Please help me reflect.',
    }

    failed_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps(payload),
        content_type='application/json',
        buffered=True,
    )
    failed_events = _sse_events(failed_response)
    assert failed_events[-1]['error_code'] == 'provider_unavailable'
    assert failed_events[-1]['retryable'] is True
    assert failed_events[-1]['retry_after_ms'] == 1000

    openai_service.return_value.chat_companion.return_value = iter(['Recovered reply'])
    retry_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps(payload),
        content_type='application/json',
        buffered=True,
    )
    assert _sse_events(retry_response)[-1]['done'] is True

    history_response = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    messages = json.loads(history_response.data)['messages']
    assert [message['message'] for message in messages] == [
        'Please help me reflect.',
        'Recovered reply',
    ]

    replay_response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps(payload),
        content_type='application/json',
        buffered=True,
    )
    replay_events = _sse_events(replay_response)
    replay_chunks = [event['chunk'] for event in replay_events if event.get('chunk')]
    assert replay_chunks == ['Recovered reply']

    replayed_history = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert len(json.loads(replayed_history.data)['messages']) == 2

    report_response = client.get(
        '/api/chat/observability/report',
        headers={'Authorization': f'Bearer {token}'},
    )
    report = json.loads(report_response.data)
    assert report['event_counts']['failed'] == 1
    assert report['event_counts']['completed'] == 2
    assert report['error_counts']['provider_unavailable'] == 1
    assert report['slo_summary']['status'] == 'breached'
    assert 'success_completion_rate' in report['slo_summary']['breached']
    assert 'error_rate' in report['slo_summary']['breached']
    assert report['slo_status']['success_completion_rate']['met'] is False
    assert report['slo_status']['error_rate']['met'] is False
    assert {
        alert['metric']: alert['severity']
        for alert in report['slo_alerts']
    } == {
        'success_completion_rate': 'critical',
        'error_rate': 'critical',
    }


def test_chat_user_isolation_by_token(client):
    token_a = _register_and_get_token(client, 'chat_user_a')
    token_b = _register_and_get_token(client, 'chat_user_b')
    conversation_id = str(uuid4())

    send_a = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token_a}'},
        data=json.dumps({'conversation_id': conversation_id, 'message': 'User A secret'}),
        content_type='application/json',
        buffered=True,
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


def test_chat_daily_budget_rejects_before_openai(client, mocked_chat_services):
    token = _register_and_get_token(client, 'chat_budget_user')
    conversation_id = str(uuid4())
    client.application.config['CHAT_DAILY_TOKEN_BUDGET'] = 100

    db_path = client.application.config['DATABASE_PATH']
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (
                user_id, conversation_id, role, content, token_count, created_at
            ) VALUES (1, ?, 'assistant', 'prior usage', 100, CURRENT_TIMESTAMP)
            """,
            (conversation_id,),
        )

    response = client.post(
        '/api/chat/message',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'conversation_id': conversation_id, 'message': 'Hello'}),
        content_type='application/json',
    )

    assert response.status_code == 429
    assert json.loads(response.data) == {
        'error': 'Daily chat limit reached. Resets at midnight.',
    }
    _, openai_service = mocked_chat_services
    openai_service.assert_not_called()

    report_response = client.get(
        '/api/chat/observability/report',
        headers={'Authorization': f'Bearer {token}'},
    )
    report = json.loads(report_response.data)
    assert report['event_counts']['token_budget_exceeded'] == 1
    assert report['error_counts']['daily_token_budget_exceeded'] == 1


def test_chat_history_returns_only_last_50_messages(client):
    token = _register_and_get_token(client, 'chat_history_limit_user')
    conversation_id = str(uuid4())
    db_path = client.application.config['DATABASE_PATH']
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO chat_messages (user_id, conversation_id, role, content, token_count)
            VALUES (1, ?, 'user', ?, 1)
            """,
            [(conversation_id, f'message-{index:02d}') for index in range(60)],
        )

    response = client.get(
        f'/api/chat/history?conversation_id={conversation_id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    messages = json.loads(response.data)['messages']
    assert len(messages) == 50
    assert messages[0]['message'] == 'message-10'
    assert messages[-1]['message'] == 'message-59'


def test_chat_rate_limit_is_applied_per_user(client):
    token = _register_and_get_token(client, 'chat_rate_user')
    client.application.config['RATELIMIT_ENABLED'] = True
    client.application.config['CHAT_RATE_LIMIT'] = '2 per hour'
    limiter.reset()

    responses = []
    for index in range(3):
        responses.append(client.post(
            '/api/chat/message',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps({
                'conversation_id': str(uuid4()),
                'message': f'Hello {index}',
            }),
            content_type='application/json',
            buffered=True,
        ))

    assert [response.status_code for response in responses] == [200, 200, 429]
    assert json.loads(responses[-1].data) == {
        'error': 'Rate limit exceeded. Try again in 60 minutes.',
    }

    report_response = client.get(
        '/api/chat/observability/report',
        headers={'Authorization': f'Bearer {token}'},
    )
    report = json.loads(report_response.data)
    assert report['event_counts']['rate_limited'] == 1
    assert report['error_counts']['rate_limit_exceeded'] == 1
    assert report['slo_summary']['status'] == 'breached'
    assert 'rate_limit_events' in report['slo_summary']['breached']
    assert {
        alert['metric']: alert['severity']
        for alert in report['slo_alerts']
    } == {
        'success_completion_rate': 'critical',
        'error_rate': 'critical',
        'rate_limit_events': 'warning',
    }
    client.application.config['RATELIMIT_ENABLED'] = False


def test_chat_observability_report_validation(client):
    token = _register_and_get_token(client, 'chat_report_validation_user')

    response = client.get(
        '/api/chat/observability/report?days=not-a-number',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 400
    assert json.loads(response.data) == {'error': 'days must be a number'}

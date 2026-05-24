# server/tests/test_import.py
# Tests for the import blueprint: template download, file upload, history
import io
import json
import os
import sqlite3
import tempfile

import pytest

from app import create_app


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Test client backed by an isolated in-memory-style SQLite database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'
    os.environ['OPENAI_API_KEY'] = 'test-key'

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as test_client:
        conn = sqlite3.connect(db_path)

        conn.execute('''
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
        ''')

        conn.execute('''
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date DATE,
                entry_number INTEGER,
                title TEXT,
                user_message TEXT,
                ai_response TEXT,
                daily_people_names TEXT,
                tags TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        conn.execute('''
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date DATE,
                entry_number INTEGER,
                title TEXT,
                cast TEXT,
                location TEXT,
                period TEXT,
                emotion TEXT,
                plot TEXT,
                symbols_and_imagery TEXT,
                insight TEXT,
                action TEXT,
                other TEXT,
                summary TEXT,
                interpretation TEXT,
                image_prompt TEXT,
                image_url TEXT,
                dream_people_names TEXT,
                tags TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()
        conn.close()

        yield test_client

    os.close(db_fd)
    os.unlink(db_path)


def _get_token(client):
    """Register a user and return a JWT token."""
    resp = client.post(
        '/api/register',
        data=json.dumps({'username': 'importer', 'password': 'pass1234'}),
        content_type='application/json'
    )
    return json.loads(resp.data)['token']


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


def _make_xlsx(daily_rows=None, dream_rows=None):
    """Build a minimal in-memory .xlsx file using openpyxl."""
    import openpyxl
    wb = openpyxl.Workbook()

    daily_ws = wb.active
    daily_ws.title = 'Daily Entries'
    daily_ws.append(['entry_date', 'title', 'content', 'tags', 'people'])
    for row in (daily_rows or []):
        daily_ws.append(row)

    dream_ws = wb.create_sheet('Dream Entries')
    dream_ws.append(['entry_date', 'title', 'plot', 'cast', 'location', 'period',
                     'emotion', 'symbols_and_imagery', 'insight', 'action', 'other', 'tags'])
    for row in (dream_rows or []):
        dream_ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── Template download ─────────────────────────────────────────────────────────

def test_template_download_requires_auth(client):
    resp = client.get('/api/import/template')
    assert resp.status_code == 401


def test_template_download_returns_xlsx(client):
    token = _get_token(client)
    resp = client.get('/api/import/template', headers=_auth_headers(token))
    assert resp.status_code == 200
    assert 'spreadsheetml' in resp.content_type or resp.content_type == \
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


# ── Upload ────────────────────────────────────────────────────────────────────

def test_upload_requires_auth(client):
    resp = client.post('/api/import/upload')
    assert resp.status_code == 401


def test_upload_missing_file(client):
    token = _get_token(client)
    resp = client.post('/api/import/upload', headers=_auth_headers(token))
    assert resp.status_code == 400
    assert b'No file' in resp.data


def test_upload_invalid_extension(client):
    token = _get_token(client)
    data = {'file': (io.BytesIO(b'dummy content'), 'test.csv')}
    resp = client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data=data,
        content_type='multipart/form-data'
    )
    assert resp.status_code == 400
    body = json.loads(resp.data)
    assert 'Invalid file type' in body.get('error', '')


def test_upload_empty_file(client):
    token = _get_token(client)
    data = {'file': (io.BytesIO(b''), 'empty.xlsx')}
    resp = client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data=data,
        content_type='multipart/form-data'
    )
    assert resp.status_code == 400
    body = json.loads(resp.data)
    assert 'empty' in body.get('error', '').lower()


def test_upload_valid_daily_entries(client):
    token = _get_token(client)
    xlsx = _make_xlsx(daily_rows=[
        ['2025-06-01', 'A good day', 'Went for a walk.', 'mood', 'Alice'],
        ['2025-06-02', 'Another day', 'Read a book.', 'reading', ''],
    ])
    data = {'file': (xlsx, 'import.xlsx')}
    resp = client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data=data,
        content_type='multipart/form-data'
    )
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body['status'] == 'success'
    assert body['imported_count'] == 2
    assert body['skipped_count'] == 0
    assert body['error_count'] == 0


def test_upload_duplicate_entry_skipped(client):
    token = _get_token(client)

    # First upload
    xlsx1 = _make_xlsx(daily_rows=[['2025-07-01', 'Day 1', 'Content', '', '']])
    client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data={'file': (xlsx1, 'first.xlsx')},
        content_type='multipart/form-data'
    )

    # Second upload with the same date
    xlsx2 = _make_xlsx(daily_rows=[['2025-07-01', 'Day 1 again', 'More content', '', '']])
    resp = client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data={'file': (xlsx2, 'second.xlsx')},
        content_type='multipart/form-data'
    )
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body['skipped_count'] == 1
    assert body['imported_count'] == 0


def test_upload_invalid_date_row_errors(client):
    token = _get_token(client)
    xlsx = _make_xlsx(daily_rows=[['not-a-date', 'Title', 'Content', '', '']])
    data = {'file': (xlsx, 'bad_date.xlsx')}
    resp = client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data=data,
        content_type='multipart/form-data'
    )
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body['error_count'] == 1
    assert len(body['errors']) > 0


def test_upload_dream_entries(client):
    token = _get_token(client)
    xlsx = _make_xlsx(dream_rows=[
        ['2025-08-10', 'Flying Dream', 'I flew over mountains.', 'Stranger',
         'Mountaintop', 'Night', 'Exhilaration', 'Wings', 'Freedom', '', '', 'dream']
    ])
    resp = client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data={'file': (xlsx, 'dreams.xlsx')},
        content_type='multipart/form-data'
    )
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert body['imported_count'] == 1
    assert body['status'] == 'success'


# ── History ───────────────────────────────────────────────────────────────────

def test_history_requires_auth(client):
    resp = client.get('/api/import/history')
    assert resp.status_code == 401


def test_history_empty_before_uploads(client):
    token = _get_token(client)
    resp = client.get('/api/import/history', headers=_auth_headers(token))
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert isinstance(body, list)
    assert len(body) == 0


def test_history_populated_after_upload(client):
    token = _get_token(client)
    xlsx = _make_xlsx(daily_rows=[['2025-09-01', 'History Test', 'Content', '', '']])
    client.post(
        '/api/import/upload',
        headers=_auth_headers(token),
        data={'file': (xlsx, 'history_test.xlsx')},
        content_type='multipart/form-data'
    )

    resp = client.get('/api/import/history', headers=_auth_headers(token))
    assert resp.status_code == 200
    body = json.loads(resp.data)
    assert len(body) == 1
    record = body[0]
    assert record['filename'] == 'history_test.xlsx'
    assert record['imported_count'] == 1
    assert record['status'] == 'success'
    assert 'imported_at' in record


def test_history_isolated_between_users(client):
    """Each user only sees their own import history."""
    # Register two users
    resp1 = client.post(
        '/api/register',
        data=json.dumps({'username': 'user_a', 'password': 'pass1234'}),
        content_type='application/json'
    )
    token_a = json.loads(resp1.data)['token']

    resp2 = client.post(
        '/api/register',
        data=json.dumps({'username': 'user_b', 'password': 'pass1234'}),
        content_type='application/json'
    )
    token_b = json.loads(resp2.data)['token']

    # User A imports
    xlsx = _make_xlsx(daily_rows=[['2025-10-01', 'User A entry', 'Content', '', '']])
    client.post(
        '/api/import/upload',
        headers=_auth_headers(token_a),
        data={'file': (xlsx, 'user_a.xlsx')},
        content_type='multipart/form-data'
    )

    # User B should see no history
    resp = client.get('/api/import/history', headers=_auth_headers(token_b))
    body = json.loads(resp.data)
    assert len(body) == 0

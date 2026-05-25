# server/tests/test_import.py
# Tests for import backend validation, duplicate handling, history, and API contract
import io
import json
import os
import sqlite3
import tempfile

import openpyxl
import pytest

from app import create_app
from services.import_service import DAILY_IMPORT_HEADERS, DREAM_IMPORT_HEADERS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables needed by the import tests."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
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

        CREATE TABLE IF NOT EXISTS dailydiary_entries (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            entry_date DATE,
            entry_number INTEGER,
            title TEXT,
            user_message TEXT,
            ai_response TEXT,
            daily_people_names TEXT,
            daily_places TEXT,
            tags TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS dreamdiary_entries (
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
        );
    ''')
    conn.commit()


@pytest.fixture
def client():
    """Flask test client with isolated in-memory database."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as test_client:
        conn = sqlite3.connect(db_path)
        _create_tables(conn)
        conn.close()
        yield test_client

    os.close(db_fd)
    os.unlink(db_path)


def _register_and_login(client) -> str:
    """Register a test user and return a JWT token."""
    client.post(
        '/api/register',
        data=json.dumps({'username': 'importer', 'password': 'secret123'}),
        content_type='application/json',
    )
    resp = client.post(
        '/api/login',
        data=json.dumps({'username': 'importer', 'password': 'secret123'}),
        content_type='application/json',
    )
    return json.loads(resp.data)['token']


# ---------------------------------------------------------------------------
# Helpers to build Excel workbooks in memory
# ---------------------------------------------------------------------------

def _make_xlsx(daily_rows=None, dream_rows=None) -> bytes:
    """Create a minimal valid .xlsx workbook."""
    wb = openpyxl.Workbook()
    ws_daily = wb.active
    ws_daily.title = 'Daily'
    ws_daily.append(['date', 'title', 'content', 'tags'])
    for row in (daily_rows or []):
        ws_daily.append(row)

    ws_dreams = wb.create_sheet(title='Dreams')
    ws_dreams.append([
        'date', 'title', 'plot', 'cast', 'location',
        'period', 'emotion', 'symbols_and_imagery',
        'insight', 'action', 'other', 'tags',
    ])
    for row in (dream_rows or []):
        ws_dreams.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_xlsx_with_headers(
    daily_headers,
    dream_headers,
    daily_rows=None,
    dream_rows=None,
) -> bytes:
    """Create a workbook with explicit sheet headers for schema-contract tests."""
    wb = openpyxl.Workbook()
    ws_daily = wb.active
    ws_daily.title = 'Daily'
    ws_daily.append(daily_headers)
    for row in (daily_rows or []):
        ws_daily.append(row)

    ws_dreams = wb.create_sheet(title='Dreams')
    ws_dreams.append(dream_headers)
    for row in (dream_rows or []):
        ws_dreams.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, token: str, file_bytes: bytes, filename='test.xlsx',
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
    """POST multipart file to /api/import/upload."""
    return client.post(
        '/api/import/upload',
        headers={'Authorization': f'Bearer {token}'},
        data={'file': (io.BytesIO(file_bytes), filename, content_type)},
        content_type='multipart/form-data',
    )


def _create_legacy_import_history_table(conn: sqlite3.Connection) -> None:
    conn.executescript('''
        DROP TABLE IF EXISTS import_history;
        CREATE TABLE import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL
        );
    ''')
    conn.commit()


# ---------------------------------------------------------------------------
# File type / size validation
# ---------------------------------------------------------------------------

class TestFileValidation:
    def test_missing_file_part(self, client):
        token = _register_and_login(client)
        resp = client.post(
            '/api/import/upload',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data['status'] == 'error'
        assert data['errors']

    def test_no_filename(self, client):
        token = _register_and_login(client)
        resp = client.post(
            '/api/import/upload',
            headers={'Authorization': f'Bearer {token}'},
            data={'file': (io.BytesIO(b''), '', 'application/octet-stream')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        data = json.loads(resp.data)
        assert data['status'] == 'error'

    def test_wrong_extension_rejected(self, client):
        token = _register_and_login(client)
        resp = _upload(client, token, b'dummy content', filename='diary.csv',
                       content_type='text/csv')
        assert resp.status_code == 422
        data = json.loads(resp.data)
        assert data['status'] == 'error'
        # Error message must mention the invalid type
        combined = ' '.join(data['errors'])
        assert 'csv' in combined.lower() or 'invalid file type' in combined.lower()

    def test_txt_extension_rejected(self, client):
        token = _register_and_login(client)
        resp = _upload(client, token, b'plain text', filename='diary.txt',
                       content_type='text/plain')
        assert resp.status_code == 422
        data = json.loads(resp.data)
        assert data['status'] == 'error'

    def test_oversized_file_rejected(self, client):
        from services.import_service import MAX_FILE_SIZE_BYTES
        token = _register_and_login(client)
        big_bytes = b'x' * (MAX_FILE_SIZE_BYTES + 1)
        resp = _upload(client, token, big_bytes, filename='big.xlsx')
        assert resp.status_code == 422
        data = json.loads(resp.data)
        assert data['status'] == 'error'
        combined = ' '.join(data['errors'])
        assert 'size' in combined.lower() or 'limit' in combined.lower()

    def test_empty_file_rejected(self, client):
        token = _register_and_login(client)
        resp = _upload(client, token, b'', filename='empty.xlsx')
        assert resp.status_code == 422
        data = json.loads(resp.data)
        assert data['status'] == 'error'

    def test_xlsx_extension_accepted(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-01-10', 'Day one', 'Good day', 'mood']])
        resp = _upload(client, token, file_bytes, filename='diary.xlsx')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] in ('success', 'empty', 'skipped')

    def test_unauthenticated_upload_rejected(self, client):
        file_bytes = _make_xlsx()
        resp = client.post(
            '/api/import/upload',
            data={'file': (io.BytesIO(file_bytes), 'test.xlsx')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Successful import
# ---------------------------------------------------------------------------

class TestSuccessfulImport:
    def test_daily_entries_inserted(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[
            ['2024-02-01', 'Morning', 'Woke up early', 'morning,routine'],
            ['2024-02-02', 'Afternoon', 'Had lunch', 'food'],
        ])
        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'success'
        assert data['summary']['inserted_daily'] == 2
        assert data['summary']['skipped_daily'] == 0
        assert data['import_id'] is not None

    def test_dream_entries_inserted(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(dream_rows=[
            ['2024-03-01', 'Flying', 'I was flying', '', '', '', 'joy', '', '', '', '', ''],
        ])
        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'success'
        assert data['summary']['inserted_dreams'] == 1

    def test_mixed_entries_inserted(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(
            daily_rows=[['2024-04-01', 'Entry 1', 'Content', 'tag1']],
            dream_rows=[['2024-04-02', 'Dream 1', 'Plot', '', '', '', '', '', '', '', '', '']],
        )
        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['summary']['inserted_daily'] == 1
        assert data['summary']['inserted_dreams'] == 1

    def test_response_shape(self, client):
        """Verify the API contract: all required fields are present."""
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-05-01', 'Shape test', 'body', '']])
        resp = _upload(client, token, file_bytes)
        data = json.loads(resp.data)

        assert 'status' in data
        assert 'summary' in data
        assert 'warnings' in data
        assert 'import_id' in data

        summary = data['summary']
        for key in ('inserted_daily', 'skipped_daily',
                    'inserted_dreams', 'skipped_dreams',
                    'duplicate_dates_daily', 'duplicate_dates_dreams'):
            assert key in summary, f'Missing key in summary: {key}'

        assert isinstance(data['warnings'], list)


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------

class TestDuplicateHandling:
    def test_duplicate_daily_entry_skipped(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-06-01', 'First', 'Body', '']])
        # First upload
        _upload(client, token, file_bytes)
        # Second upload — same date
        resp = _upload(client, token, file_bytes)
        data = json.loads(resp.data)
        assert data['summary']['inserted_daily'] == 0
        assert data['summary']['skipped_daily'] == 1
        assert '2024-06-01' in data['summary']['duplicate_dates_daily']

    def test_duplicate_reported_in_warnings(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-07-01', 'T', 'B', '']])
        _upload(client, token, file_bytes)
        resp = _upload(client, token, file_bytes)
        data = json.loads(resp.data)
        # At least one warning should mention the duplicate
        combined = ' '.join(data['warnings'])
        assert '2024-07-01' in combined or 'skipped' in combined.lower()

    def test_partial_duplicate(self, client):
        """One existing date + one new date → only new one inserted."""
        token = _register_and_login(client)
        file1 = _make_xlsx(daily_rows=[['2024-08-01', 'Existing', 'Body', '']])
        _upload(client, token, file1)

        file2 = _make_xlsx(daily_rows=[
            ['2024-08-01', 'Dup', 'Should skip', ''],
            ['2024-08-02', 'New', 'Should insert', ''],
        ])
        resp = _upload(client, token, file2)
        data = json.loads(resp.data)
        assert data['summary']['inserted_daily'] == 1
        assert data['summary']['skipped_daily'] == 1

    def test_all_duplicates_returns_skipped_status(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-09-01', 'T', 'B', '']])
        _upload(client, token, file_bytes)
        resp = _upload(client, token, file_bytes)
        data = json.loads(resp.data)
        assert data['status'] == 'skipped'


# ---------------------------------------------------------------------------
# Invalid / malformed data rows
# ---------------------------------------------------------------------------

class TestMalformedData:
    def test_invalid_date_row_skipped_with_warning(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[
            ['not-a-date', 'Bad row', 'Should be skipped', ''],
            ['2024-10-01', 'Good row', 'Should be inserted', ''],
        ])
        resp = _upload(client, token, file_bytes)
        data = json.loads(resp.data)
        assert data['summary']['inserted_daily'] == 1
        combined = ' '.join(data['warnings'])
        assert 'skipped' in combined.lower() or 'invalid' in combined.lower()

    def test_empty_workbook_no_data(self, client):
        """Workbook with correct sheets but no data rows → status empty."""
        token = _register_and_login(client)
        file_bytes = _make_xlsx()  # headers only, no data rows
        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'empty'
        assert data['summary']['inserted_daily'] == 0
        assert data['summary']['inserted_dreams'] == 0

    def test_injection_stripped_from_content(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[
            ['2024-11-01', '<script>alert(1)</script>', 'javascript:alert(1)', 'tag'],
        ])
        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['summary']['inserted_daily'] == 1
        # Verify database stored sanitised values
        db_path = os.environ['DB_PATH']
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT title, user_message FROM dailydiary_entries WHERE entry_date = '2024-11-01'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert '<script>' not in row['title']
        assert 'javascript:' not in row['user_message']


# ---------------------------------------------------------------------------
# Schema contract regression coverage (Issue #39)
# ---------------------------------------------------------------------------

class TestSchemaContractWarnings:
    def test_daily_unexpected_column_emits_warning(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx_with_headers(
            daily_headers=['date', 'title', 'content', 'tags', 'mood_score'],
            dream_headers=list(DREAM_IMPORT_HEADERS),
            daily_rows=[['2025-03-01', 'T', 'Body', 'tag', '9']],
        )

        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        combined = ' '.join(data['warnings']).lower()

        assert 'daily sheet' in combined
        assert 'unexpected columns' in combined
        assert 'mood_score' in combined

    def test_daily_missing_required_column_warning(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx_with_headers(
            daily_headers=['date', 'title', 'tags'],
            dream_headers=list(DREAM_IMPORT_HEADERS),
            daily_rows=[['2025-03-02', 'No content column', 'tag']],
        )

        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        combined = ' '.join(data['warnings']).lower()

        assert 'daily sheet' in combined
        assert 'missing columns' in combined
        assert 'content' in combined

    def test_daily_missing_date_leads_to_skipped_rows_zero_inserted(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx_with_headers(
            daily_headers=list(DAILY_IMPORT_HEADERS),
            dream_headers=list(DREAM_IMPORT_HEADERS),
            daily_rows=[[None, 'Missing date', 'Body', 'tag']],
        )

        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        combined = ' '.join(data['warnings']).lower()

        assert data['summary']['inserted_daily'] == 0
        assert data['summary']['skipped_daily'] == 0
        assert 'daily sheet row' in combined
        assert 'invalid or missing date' in combined

    def test_dreams_unexpected_column_emits_warning(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx_with_headers(
            daily_headers=list(DAILY_IMPORT_HEADERS),
            dream_headers=[*DREAM_IMPORT_HEADERS, 'lucidity_level'],
            dream_rows=[[
                '2025-03-03', 'Dream', 'Plot', '', '', '', 'joy', '', '', '', '', '', 'high'
            ]],
        )

        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        combined = ' '.join(data['warnings']).lower()

        assert 'dreams sheet' in combined
        assert 'unexpected columns' in combined
        assert 'lucidity_level' in combined

    def test_dreams_missing_plot_warning(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx_with_headers(
            daily_headers=list(DAILY_IMPORT_HEADERS),
            dream_headers=[
                'date',
                'title',
                'cast',
                'location',
                'period',
                'emotion',
                'symbols_and_imagery',
                'insight',
                'action',
                'other',
                'tags',
            ],
            dream_rows=[['2025-03-04', 'Dream title', '', '', '', '', '', '', '', '', 'tag']],
        )

        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        combined = ' '.join(data['warnings']).lower()

        assert 'dreams sheet' in combined
        assert 'missing columns' in combined
        assert 'plot' in combined

    def test_warnings_payload_is_list_of_strings(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx_with_headers(
            daily_headers=['date', 'title', 'content', 'tags', 'bonus_column'],
            dream_headers=list(DREAM_IMPORT_HEADERS),
            daily_rows=[['2025-03-05', 'Payload shape', 'Body', 'tag', 'extra']],
        )

        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)

        assert isinstance(data['warnings'], list)
        assert data['warnings'], 'Expected at least one warning for schema mismatch.'
        assert all(isinstance(item, str) for item in data['warnings'])


# ---------------------------------------------------------------------------
# Import history
# ---------------------------------------------------------------------------

class TestImportHistory:
    def test_history_empty_initially(self, client):
        token = _register_and_login(client)
        resp = client.get(
            '/api/import/history',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'history' in data
        assert data['history'] == []

    def test_history_recorded_after_upload(self, client):
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-12-01', 'Entry', 'Body', '']])
        _upload(client, token, file_bytes, filename='myfile.xlsx')
        resp = client.get(
            '/api/import/history',
            headers={'Authorization': f'Bearer {token}'},
        )
        data = json.loads(resp.data)
        assert len(data['history']) == 1
        record = data['history'][0]
        assert record['filename'] == 'myfile.xlsx'
        assert record['inserted_daily'] == 1
        assert record['status'] == 'success'

    def test_history_row_shape(self, client):
        """Verify every expected field is present in history records."""
        token = _register_and_login(client)
        file_bytes = _make_xlsx(daily_rows=[['2024-12-02', 'T', 'B', '']])
        _upload(client, token, file_bytes)
        resp = client.get(
            '/api/import/history',
            headers={'Authorization': f'Bearer {token}'},
        )
        data = json.loads(resp.data)
        record = data['history'][0]
        required_keys = {
            'id', 'imported_at', 'filename', 'file_size_bytes',
            'inserted_daily', 'skipped_daily',
            'inserted_dreams', 'skipped_dreams',
            'warnings', 'status',
        }
        assert required_keys.issubset(record.keys()), (
            f"Missing keys: {required_keys - record.keys()}"
        )
        assert isinstance(record['warnings'], list)

    def test_history_multiple_uploads(self, client):
        token = _register_and_login(client)
        for day in ('2025-01-01', '2025-01-02', '2025-01-03'):
            file_bytes = _make_xlsx(daily_rows=[[day, 'T', 'B', '']])
            _upload(client, token, file_bytes)
        resp = client.get(
            '/api/import/history',
            headers={'Authorization': f'Bearer {token}'},
        )
        data = json.loads(resp.data)
        assert len(data['history']) == 3

    def test_history_unauthenticated(self, client):
        resp = client.get('/api/import/history')
        assert resp.status_code == 401

    def test_history_isolated_per_user(self, client):
        """Two users should each see only their own history."""
        # User 1
        client.post('/api/register',
                    data=json.dumps({'username': 'userA', 'password': 'pw'}),
                    content_type='application/json')
        r = client.post('/api/login',
                        data=json.dumps({'username': 'userA', 'password': 'pw'}),
                        content_type='application/json')
        token_a = json.loads(r.data)['token']

        # User 2
        client.post('/api/register',
                    data=json.dumps({'username': 'userB', 'password': 'pw'}),
                    content_type='application/json')
        r = client.post('/api/login',
                        data=json.dumps({'username': 'userB', 'password': 'pw'}),
                        content_type='application/json')
        token_b = json.loads(r.data)['token']

        # User A uploads
        file_bytes = _make_xlsx(daily_rows=[['2025-02-01', 'T', 'B', '']])
        _upload(client, token_a, file_bytes)

        # User B should see empty history
        resp_b = client.get('/api/import/history',
                            headers={'Authorization': f'Bearer {token_b}'})
        data_b = json.loads(resp_b.data)
        assert data_b['history'] == []

    def test_legacy_history_table_is_repaired_on_upload(self, client):
        token = _register_and_login(client)
        db_path = os.environ['DB_PATH']
        conn = sqlite3.connect(db_path)
        _create_legacy_import_history_table(conn)
        conn.close()

        file_bytes = _make_xlsx(daily_rows=[['2025-02-02', 'Legacy', 'Body', '']])
        resp = _upload(client, token, file_bytes)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'success'

        history_resp = client.get(
            '/api/import/history',
            headers={'Authorization': f'Bearer {token}'},
        )
        history_data = json.loads(history_resp.data)
        assert len(history_data['history']) == 1
        assert history_data['history'][0]['imported_at']


# ---------------------------------------------------------------------------
# Template download
# ---------------------------------------------------------------------------

class TestTemplateDownload:
    def test_template_returns_xlsx(self, client):
        token = _register_and_login(client)
        resp = client.get(
            '/api/import/template',
            headers={'Authorization': f'Bearer {token}'},
        )
        assert resp.status_code == 200
        assert 'spreadsheet' in resp.content_type or 'octet-stream' in resp.content_type

    def test_template_has_correct_sheets(self, client):
        token = _register_and_login(client)
        resp = client.get(
            '/api/import/template',
            headers={'Authorization': f'Bearer {token}'},
        )
        wb = openpyxl.load_workbook(io.BytesIO(resp.data))
        assert 'Daily' in wb.sheetnames
        assert 'Dreams' in wb.sheetnames

    def test_template_has_daily_headers(self, client):
        token = _register_and_login(client)
        resp = client.get(
            '/api/import/template',
            headers={'Authorization': f'Bearer {token}'},
        )
        wb = openpyxl.load_workbook(io.BytesIO(resp.data))
        ws = wb['Daily']
        headers = [cell.value for cell in ws[1]]
        assert headers == list(DAILY_IMPORT_HEADERS)

    def test_template_has_dreams_headers(self, client):
        token = _register_and_login(client)
        resp = client.get(
            '/api/import/template',
            headers={'Authorization': f'Bearer {token}'},
        )
        wb = openpyxl.load_workbook(io.BytesIO(resp.data))
        ws = wb['Dreams']
        headers = [cell.value for cell in ws[1]]
        assert headers == list(DREAM_IMPORT_HEADERS)

    def test_template_unauthenticated(self, client):
        resp = client.get('/api/import/template')
        assert resp.status_code == 401

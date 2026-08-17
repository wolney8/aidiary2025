# server/tests/test_entries.py
# Entries CRUD tests
import pytest
import json
import sqlite3
from app import create_app
import tempfile
import os
import shutil
import base64
from datetime import date
from io import BytesIO
from unittest.mock import patch, MagicMock
from routes.analyse import ANALYSE_TEXT_MAX_LENGTH
from routes.entries import _coerce_search_text, _parse_entry_date, _sql
from services.openai_svc import AnalysisRateLimitError
from PIL import Image

@pytest.fixture
def client():
    """Create test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    os.environ['DB_PATH'] = db_path
    os.environ['MEDIA_ROOT'] = media_root
    os.environ['JWT_SECRET'] = 'test-secret'
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['AUTH_LOGIN_RATE_LIMIT'] = '1000 per minute'
    os.environ['AUTH_REGISTER_RATE_LIMIT'] = '1000 per minute'
    os.environ['ANALYSE_RATE_LIMIT'] = '1000 per minute'
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Create tables in test database
        import sqlite3
        conn = sqlite3.connect(db_path)
        
        # Create users table
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
        
        # Create dailydiary_entries table
        conn.execute('''
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date DATE,
                entry_time TEXT,
                entry_number INTEGER,
                title TEXT,
                user_message TEXT,
                ai_response TEXT,
                image_prompt TEXT,
                image_url TEXT,
                image_storage_key TEXT,
                image_source TEXT,
                recycled_image_prompt TEXT,
                image_position_x REAL DEFAULT 50,
                image_position_y REAL DEFAULT 50,
                daily_people_names TEXT,
                daily_places TEXT,
                tags TEXT,
                mood TEXT,
                ai_style TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Create dreamdiary_entries table
        conn.execute('''
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date DATE,
                entry_time TEXT,
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
                image_storage_key TEXT,
                image_source TEXT,
                recycled_image_prompt TEXT,
                image_position_x REAL DEFAULT 50,
                image_position_y REAL DEFAULT 50,
                dream_people_names TEXT,
                dream_places TEXT,
                tags TEXT,
                mood TEXT,
                ai_style TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        
        conn.commit()
        conn.close()
        
        yield client
    
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(media_root)


@pytest.fixture
def client_schema_without_mood_columns():
    """Create test client where diary tables start without mood/ai_style columns."""
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    os.environ['DB_PATH'] = db_path
    os.environ['MEDIA_ROOT'] = media_root
    os.environ['JWT_SECRET'] = 'test-secret'
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['AUTH_LOGIN_RATE_LIMIT'] = '1000 per minute'
    os.environ['AUTH_REGISTER_RATE_LIMIT'] = '1000 per minute'
    os.environ['ANALYSE_RATE_LIMIT'] = '1000 per minute'

    import sqlite3
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
            daily_places TEXT,
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
            recycled_image_prompt TEXT,
            dream_people_names TEXT,
            dream_places TEXT,
            tags TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')


    conn.commit()
    conn.close()

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(media_root)


@pytest.fixture
def client_schema_without_analysis_columns():
    """Create test client where analysis result columns are missing initially."""
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    os.environ['DB_PATH'] = db_path
    os.environ['MEDIA_ROOT'] = media_root
    os.environ['JWT_SECRET'] = 'test-secret'
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['AUTH_LOGIN_RATE_LIMIT'] = '1000 per minute'
    os.environ['AUTH_REGISTER_RATE_LIMIT'] = '1000 per minute'
    os.environ['ANALYSE_RATE_LIMIT'] = '1000 per minute'

    import sqlite3
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
            daily_people_names TEXT,
            daily_places TEXT,
            tags TEXT,
            mood TEXT,
            ai_style TEXT,
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
            dream_people_names TEXT,
            dream_places TEXT,
            tags TEXT,
            mood TEXT,
            ai_style TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

    app = create_app()
    app.config['TESTING'] = True

    with app.test_client() as client:
        yield client

    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(media_root)

def get_auth_token(client):
    """Helper to get authentication token."""
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )
    data = json.loads(response.data)
    return data['token']


def grant_ai_media_access(user_id: int = 1) -> None:
    """Give a test user enough quota to exercise AI media behaviours."""
    with sqlite3.connect(os.environ['DB_PATH']) as conn:
        conn.execute(
            """
            INSERT INTO entitlements (user_id, tier, source, status)
            VALUES (?, 'administrator', 'manual', 'active')
            ON CONFLICT(user_id) DO UPDATE SET
                tier = 'administrator',
                source = 'manual',
                status = 'active'
            """,
            (user_id,),
        )


def create_test_image_bytes(
    size: tuple[int, int] = (1200, 900),
    color: tuple[int, int, int] = (64, 128, 196),
    format_name: str = 'PNG',
) -> bytes:
    image = Image.new('RGB', size, color)
    buffer = BytesIO()
    image.save(buffer, format=format_name)
    return buffer.getvalue()


def seed_bulk_delete_entries(client, token: str) -> None:
    client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-01',
            'user_message': 'Daily bulk delete seed'
        }),
        content_type='application/json'
    )
    with sqlite3.connect(os.environ['DB_PATH']) as conn:
        conn.execute(
            """
            INSERT INTO important_days (
                user_id, label, starts_on, month, day, original_year,
                category, recurrence, icon_name, accent_color, note
            )
            VALUES (1, 'Bulk delete important day', '2026-05-02', 5, 2, 2026,
                    'milestone', 'yearly', 'event', 'blue', 'seed')
            """
        )
        conn.execute(
            """
            INSERT INTO cbt_worksheets (
                user_id, worksheet_type, title, status, current_step, record_date
            )
            VALUES (1, 'thought_record', 'Bulk delete thought record',
                    'completed', 7, '2026-05-04')
            """
        )
        worksheet_id = conn.execute('SELECT MAX(id) FROM cbt_worksheets').fetchone()[0]
        conn.execute(
            """
            INSERT INTO cbt_thought_record_data (
                worksheet_id, situation, balanced_thought
            )
            VALUES (?, 'Bulk delete situation', 'Bulk delete balanced thought')
            """,
            (worksheet_id,),
        )
    client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-03',
            'title': 'Dream seed',
            'plot': 'Dream bulk delete seed'
        }),
        content_type='application/json'
    )


def test_search_date_parser_accepts_postgres_date_objects():
    parsed = _parse_entry_date(date(2026, 8, 16))

    assert parsed is not None
    assert parsed.date().isoformat() == '2026-08-16'


def test_search_text_coercion_handles_structured_values():
    assert _coerce_search_text(None) == ''
    assert _coerce_search_text(['Daylio', 'car']) == 'Daylio, car'
    assert _coerce_search_text({'source': 'Daylio'}) == '{"source": "Daylio"}'


def test_entries_sql_helper_adapts_placeholders_for_postgres(client):
    client.application.config['DATABASE_PROVIDER'] = 'postgres'

    with client.application.app_context():
        assert _sql('SELECT * FROM dailydiary_entries WHERE user_id = ?') == (
            'SELECT * FROM dailydiary_entries WHERE user_id = %s'
        )


def test_search_supports_multi_word_queries(client):
    token = get_auth_token(client)
    client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-08-16',
            'title': 'Car reflection',
            'user_message': 'A Daylio import mentioned the car journey home.',
            'tags': 'Daylio, car',
        }),
        content_type='application/json'
    )

    response = client.get(
        '/api/search?q=daylio%20car',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body['results']
    assert body['results'][0]['entry_date'] == '2026-08-16'


def test_search_multi_word_queries_require_each_exact_token(client):
    token = get_auth_token(client)
    entries = [
        {
            'entry_date': '2026-08-16',
            'title': 'Car day',
            'user_message': 'This was a car day. The car was useful all day.',
            'tags': 'car, day',
        },
        {
            'entry_date': '2026-08-17',
            'title': 'Day with the car',
            'user_message': 'The day included a useful car journey.',
            'tags': 'car, day',
        },
        {
            'entry_date': '2026-08-15',
            'title': 'Care day',
            'user_message': 'Care plans took all day.',
            'tags': 'care, day',
        },
        {
            'entry_date': '2026-08-14',
            'title': 'Card day',
            'user_message': 'Card games took all day.',
            'tags': 'card, day',
        },
        {
            'entry_date': '2026-08-13',
            'title': 'Carry day',
            'user_message': 'Carry bags all day.',
            'tags': 'carry, day',
        },
        {
            'entry_date': '2026-08-12',
            'title': 'Car only',
            'user_message': 'The car was mentioned without the second term.',
            'tags': 'car',
        },
    ]
    for entry in entries:
        client.post(
            '/api/daily',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps(entry),
            content_type='application/json',
        )

    response = client.get(
        '/api/search?q=car%20day',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert [result['title'] for result in body['results']] == ['Car day', 'Day with the car']
    title_match = body['results'][0]['matches']['title'].lower()
    body_match = body['results'][0]['matches']['body'].lower()
    assert 'car</span>' in title_match
    assert 'day</span>' in title_match
    assert 'car</span>' in body_match
    assert 'day</span>' in body_match


def test_search_quoted_phrase_requires_exact_phrase(client):
    token = get_auth_token(client)
    for entry in [
        {
            'entry_date': '2026-08-16',
            'title': 'Car day',
            'user_message': 'This was a car day.',
            'tags': 'car, day',
        },
        {
            'entry_date': '2026-08-17',
            'title': 'Day with the car',
            'user_message': 'The day included a useful car journey.',
            'tags': 'car, day',
        },
    ]:
        client.post(
            '/api/daily',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps(entry),
            content_type='application/json',
        )

    response = client.get(
        '/api/search?q=%22car%20day%22',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert [result['title'] for result in body['results']] == ['Car day']
    assert 'car day</span>' in body['results'][0]['matches']['body'].lower()


def test_search_comma_queries_match_any_exact_token_and_rank_both_first(client):
    token = get_auth_token(client)
    for entry in [
        {
            'entry_date': '2026-08-16',
            'title': 'Car day',
            'user_message': 'This was a car day.',
            'tags': 'car, day',
        },
        {
            'entry_date': '2026-08-15',
            'title': 'Car only',
            'user_message': 'Only the car appears here.',
            'tags': 'car',
        },
        {
            'entry_date': '2026-08-17',
            'title': 'Day only',
            'user_message': 'Only the day appears here.',
            'tags': 'day',
        },
        {
            'entry_date': '2026-08-14',
            'title': 'Care only',
            'user_message': 'Care should not match the vehicle token.',
            'tags': 'care',
        },
    ]:
        client.post(
            '/api/daily',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps(entry),
            content_type='application/json',
        )

    response = client.get(
        '/api/search?q=car,%20day',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert [result['title'] for result in body['results']] == [
        'Car day',
        'Day only',
        'Car only',
    ]


def test_search_caps_large_result_sets(client):
    token = get_auth_token(client)
    conn = sqlite3.connect(os.environ['DB_PATH'])
    conn.executemany(
        '''
        INSERT INTO dailydiary_entries (user_id, entry_date, title, user_message, tags)
        VALUES (?, ?, ?, ?, ?)
        ''',
        [
            (
                1,
                f'2026-01-{(index % 28) + 1:02d}',
                f'Daylio import {index}',
                'Daylio archive test entry',
                'Daylio',
            )
            for index in range(260)
        ],
    )
    conn.commit()
    conn.close()

    response = client.get(
        '/api/search?q=daylio',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    body = json.loads(response.data)
    assert body['truncated'] is True
    assert body['result_limit'] == 250
    assert len(body['results']) == 250


def test_create_daily_entry(client):
    """Test creating a daily entry."""
    token = get_auth_token(client)
    
    response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-01-15',
            'entry_time': '14:35',
            'user_message': 'Today was a good day'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'id' in data
    assert data['entry_time'] == '14:35'
    assert data['entry_number'] == 1


def test_create_daily_entry_persists_mood_and_ai_style(client):
    """POST /api/daily should persist mood and ai_style on initial save."""
    token = get_auth_token(client)

    create_response = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-01-16',
            'entry_time': '18:25',
            'user_message': 'Checking create persistence',
            'mood': 'thoughtful',
            'ai_style': 'reflective',
        }),
        content_type='application/json',
    )

    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    detail_response = client.get(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert detail_response.status_code == 200
    payload = json.loads(detail_response.data)
    assert payload['mood'] == 'thoughtful'
    assert payload['ai_style'] == 'reflective'


@patch('routes.entries.derive_daily_nltk_fields')
def test_create_daily_entry_merges_nltk_enrichment_on_save(mock_derive_daily, client):
    token = get_auth_token(client)
    mock_derive_daily.return_value = {
        'tags': 'work,focus',
        'daily_people_names': 'Alex',
        'daily_places': 'Office',
    }

    create_response = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-01-17',
            'title': 'Busy day',
            'user_message': 'Met Alex at the office',
            'tags': 'manual',
            'daily_people_names': 'Sam',
            'daily_places': 'Cafe',
        }),
        content_type='application/json',
    )

    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    detail_response = client.get(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    payload = json.loads(detail_response.data)

    assert payload['tags'] == 'manual,work,focus'
    assert payload['daily_people_names'] == 'Sam,Alex'
    assert payload['daily_places'] == 'Cafe,Office'


def test_bulk_delete_readiness_requires_guarded_export(client):
    token = get_auth_token(client)
    seed_bulk_delete_entries(client, token)

    response = client.get(
        '/api/entries/bulk-delete-readiness',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['has_entries'] is True
    assert data['eligible_for_delete'] is False
    assert data['first_entry_date'] == '2026-05-01'
    assert data['last_entry_date'] == '2026-05-04'
    assert data['important_day_count'] == 1
    assert data['thought_record_count'] == 1


def test_bulk_delete_rejects_without_matching_export_guard(client):
    token = get_auth_token(client)
    seed_bulk_delete_entries(client, token)

    response = client.post(
        '/api/entries/bulk-delete',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'guard_token': 'missing-token',
            'confirmation_text': 'DELETE ALL',
        }),
        content_type='application/json'
    )

    assert response.status_code == 409
    data = json.loads(response.data)
    assert 'same-session full export' in data['error']


def test_bulk_delete_succeeds_after_full_range_export(client):
    token = get_auth_token(client)
    seed_bulk_delete_entries(client, token)

    export_response = client.get(
        '/api/import/export?export_all=true',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert export_response.status_code == 200
    guard_token = export_response.headers.get('X-OpenMynd-Export-Token')
    assert guard_token

    readiness_response = client.get(
        f'/api/entries/bulk-delete-readiness?guard_token={guard_token}',
        headers={'Authorization': f'Bearer {token}'},
    )
    readiness_data = json.loads(readiness_response.data)
    assert readiness_data['eligible_for_delete'] is True

    delete_response = client.post(
        '/api/entries/bulk-delete',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'guard_token': guard_token,
            'confirmation_text': 'DELETE ALL',
        }),
        content_type='application/json'
    )

    assert delete_response.status_code == 200
    delete_data = json.loads(delete_response.data)
    assert delete_data['deleted_daily'] == 1
    assert delete_data['deleted_dreams'] == 1
    assert delete_data['deleted_important_days'] == 1
    assert delete_data['deleted_thought_records'] == 1
    assert delete_data['deleted_total'] == 4

    remaining_daily = client.get(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
    )
    remaining_dreams = client.get(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert json.loads(remaining_daily.data) == []
    assert json.loads(remaining_dreams.data) == []
    with sqlite3.connect(os.environ['DB_PATH']) as conn:
        remaining_important_days = conn.execute(
            'SELECT COUNT(*) FROM important_days WHERE user_id = 1',
        ).fetchone()[0]
        remaining_thought_records = conn.execute(
            'SELECT COUNT(*) FROM cbt_worksheets WHERE user_id = 1',
        ).fetchone()[0]
    assert remaining_important_days == 0
    assert remaining_thought_records == 0

def test_create_daily_entry_rejects_future_date(client):
    """POST /api/daily should reject future dates."""
    token = get_auth_token(client)
    future_date = '2999-01-01'

    response = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': future_date,
            'user_message': 'Future daily entry'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Future entry dates are not allowed'

def test_get_daily_entries(client):
    """Test retrieving daily entries."""
    token = get_auth_token(client)
    
    # Create an entry first
    client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'user_message': 'Test entry'
        }),
        content_type='application/json'
    )
    
    # Get entries
    response = client.get('/api/daily',
        headers={'Authorization': f'Bearer {token}'}
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0


def test_entries_overview_returns_primary_lists(client):
    """GET /api/entries/overview should combine the primary Entries page data."""
    token = get_auth_token(client)

    daily_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-06-01',
            'title': 'Overview daily',
            'user_message': 'Daily overview entry'
        }),
        content_type='application/json'
    )
    assert daily_response.status_code == 201

    dream_response = client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-06-02',
            'title': 'Overview dream',
            'plot': 'Dream overview entry'
        }),
        content_type='application/json'
    )
    assert dream_response.status_code == 201

    response = client.get('/api/entries/overview',
        headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert set(payload.keys()) == {
        'daily',
        'dreams',
        'thought_records',
        'important_days',
    }
    assert any(entry['title'] == 'Overview daily' for entry in payload['daily'])
    assert any(entry['title'] == 'Overview dream' for entry in payload['dreams'])
    assert isinstance(payload['thought_records'], list)
    assert isinstance(payload['important_days'], list)


def test_daily_list_does_not_remote_check_media(client):
    """List endpoints should not HEAD every media object; detail/download validates files."""
    token = get_auth_token(client)

    create_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-06-01',
            'user_message': 'Entry with stored media references',
        }),
        content_type='application/json',
    )
    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    with sqlite3.connect(os.environ['DB_PATH']) as conn:
        conn.execute(
            """
            UPDATE dailydiary_entries
            SET image_storage_key = 'daily/1/test-image.jpg'
            WHERE id = ?
            """,
            (entry_id,),
        )
        conn.execute(
            """
            INSERT INTO entry_assets (
                user_id, entry_type, entry_id, asset_role, storage_key,
                original_filename, mime_type, file_size_bytes
            )
            VALUES (1, 'daily', ?, 'attachment', 'daily-assets/1/test.pdf',
                    'test.pdf', 'application/pdf', 120)
            """,
            (entry_id,),
        )

    with patch('routes.entries.media_path_exists') as media_exists:
        response = client.get('/api/daily',
            headers={'Authorization': f'Bearer {token}'},
        )

    assert response.status_code == 200
    media_exists.assert_not_called()
    data = json.loads(response.data)
    entry = next(item for item in data if item['id'] == entry_id)
    assert entry['image_url']
    assert entry['attachments'] == [{'id': 1, 'mime_type': 'application/pdf'}]


def test_startup_migration_adds_missing_columns_and_daily_update_allows_mood(client_schema_without_mood_columns):
    """App startup should migrate missing daily mood/ai_style columns and allow PUT updates."""
    token = get_auth_token(client_schema_without_mood_columns)

    create_resp = client_schema_without_mood_columns.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-09', 'user_message': 'Before migration update'}),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client_schema_without_mood_columns.put(f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mood': 'calm', 'ai_style': 'concise'}),
        content_type='application/json'
    )
    assert update_resp.status_code == 200


def test_startup_migration_adds_missing_columns_and_dream_update_allows_mood(client_schema_without_mood_columns):
    """App startup should migrate missing dream mood/ai_style columns and allow PUT updates."""
    token = get_auth_token(client_schema_without_mood_columns)

    create_resp = client_schema_without_mood_columns.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-10', 'title': 'Dream', 'plot': 'Plot'}),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client_schema_without_mood_columns.put(f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mood': 'curious', 'ai_style': 'minimal'}),
        content_type='application/json'
    )
    assert update_resp.status_code == 200


def test_startup_migration_ensures_entry_ai_metadata_table(client):
    """App startup should ensure the hidden AI metadata table exists."""
    import sqlite3

    db_path = client.application.config['DATABASE_PATH']
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'entry_ai_metadata'"
        ).fetchone()

    assert row is not None


def test_startup_migration_adds_daily_ai_response_column(client_schema_without_analysis_columns):
    """App startup should add missing daily ai_response column and allow updates."""
    token = get_auth_token(client_schema_without_analysis_columns)

    create_response = client_schema_without_analysis_columns.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-11', 'user_message': 'Draft text'}),
        content_type='application/json'
    )
    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    update_response = client_schema_without_analysis_columns.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'ai_response': 'Attached analysis'}),
        content_type='application/json'
    )
    assert update_response.status_code == 200

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT ai_response FROM dailydiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    columns = {
        info[1]
        for info in conn.execute('PRAGMA table_info(dailydiary_entries)').fetchall()
    }
    conn.close()

    assert 'ai_response' in columns
    assert row[0] == 'Attached analysis'


def test_startup_migration_adds_dream_analysis_columns(client_schema_without_analysis_columns):
    """App startup should add missing dream analysis columns and allow updates."""
    token = get_auth_token(client_schema_without_analysis_columns)

    create_response = client_schema_without_analysis_columns.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-12', 'plot': 'Dream draft'}),
        content_type='application/json'
    )
    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    update_response = client_schema_without_analysis_columns.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'summary': 'Dream summary',
            'interpretation': 'Dream interpretation',
            'image_prompt': 'Moonlit forest',
        }),
        content_type='application/json'
    )
    assert update_response.status_code == 200

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT summary, interpretation, image_prompt FROM dreamdiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    columns = {
        info[1]
        for info in conn.execute('PRAGMA table_info(dreamdiary_entries)').fetchall()
    }
    conn.close()

    assert {'summary', 'interpretation', 'image_prompt', 'image_url'}.issubset(columns)
    assert row == ('Dream summary', 'Dream interpretation', 'Moonlit forest')

@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry(mock_openai, client):
    """Test AI analysis of daily entry."""
    token = get_auth_token(client)
    
    # Mock OpenAI response
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        'ai_response': 'Great reflection!',
        'tags': 'positive,growth',
        'people_names': 'John,hopefully,Sarah',
        'places': 'Cafe,Park'
    })
    mock_client.chat.completions.create.return_value = mock_response
    
    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Had lunch with John and Sarah today'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'ai_response' in data
    assert 'tags' in data
    assert 'daily_people_names' in data
    assert 'daily_places' in data
    assert data['daily_people_names'] == 'John,Sarah'


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_records_ai_usage_after_success(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)
    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'A useful reflection.',
        'tags': 'reflection',
        'people_names': '',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.return_value = {
        'tags': '',
        'daily_people_names': '',
        'daily_places': '',
    }

    response = client.post(
        '/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'A detailed entry for analysis'}),
        content_type='application/json',
    )

    assert response.status_code == 200
    db_path = client.application.config['DATABASE_PATH']
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM usage_events WHERE user_id = 1 AND event_type = 'ai_analysis'"
        ).fetchone()[0]
    assert count == 1


@patch('routes.analyse.OpenAIService')
def test_analyse_returns_upgrade_required_when_ai_limit_reached(
    mock_service_cls,
    client,
):
    token = get_auth_token(client)
    db_path = client.application.config['DATABASE_PATH']
    with sqlite3.connect(db_path) as conn:
        for _index in range(20):
            conn.execute(
                """
                INSERT INTO usage_events (user_id, event_type, units, metadata_json)
                VALUES (1, 'ai_analysis', 1, '{}')
                """
            )

    response = client.post(
        '/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'A detailed entry for analysis'}),
        content_type='application/json',
    )

    assert response.status_code == 402
    body = response.get_json()
    assert body['code'] == 'upgrade_required'
    assert body['usage']['ai_analysis']['remaining'] == 0
    mock_service_cls.assert_not_called()


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_filters_generic_people_and_places(mock_openai, client):
    token = get_auth_token(client)

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        'ai_response': 'You spent time with John and felt reflective.',
        'tags': 'reflection',
        'people_names': 'someone,John,myself,Sarah',
        'places': 'location,Cafe,unknown,Park'
    })
    mock_client.chat.completions.create.return_value = mock_response

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Had lunch with John and Sarah at the cafe and then walked in the park'
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['daily_people_names'] == 'John,Sarah'
    assert data['daily_places'] == 'Cafe,Park'


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_merges_user_and_ai_nltk_tags(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'You sounded calm after meeting Sam in London.',
        'tags': 'reflection,friendship',
        'people_names': 'Sam',
        'places': 'London',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {
            'tags': 'gym,anxiety',
            'daily_people_names': 'Alex',
            'daily_places': 'Manchester',
        },
        {
            'tags': 'calm,reflection',
            'daily_people_names': '',
            'daily_places': '',
        },
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'Met Alex after the gym in Manchester'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['tags'] == 'gym,anxiety,reflection,friendship,calm'
    assert data['daily_people_names'] == 'Alex,Sam'
    assert data['daily_places'] == 'Manchester,London'


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_filters_generic_ai_tags_from_merged_metadata(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'You felt uncertain after seeing Katie again.',
        'tags': 'analysis,daily,relationships,uncertainty',
        'people_names': 'Katie',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {
            'tags': 'evidence',
            'daily_people_names': 'Katie',
            'daily_places': '',
        },
        {
            'tags': 'entry,reflection',
            'daily_people_names': '',
            'daily_places': '',
        },
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'I saw Katie again and felt uncertain.'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['tags'] == 'evidence,relationships,uncertainty,reflection'
    assert data['daily_people_names'] == 'Katie'


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_passes_ai_style_and_user_preferences_to_service(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)
    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    for statement in (
        "ALTER TABLE users ADD COLUMN ai_tone TEXT",
        "ALTER TABLE users ADD COLUMN ai_verbosity TEXT",
        "ALTER TABLE users ADD COLUMN ai_focus TEXT",
        "ALTER TABLE users ADD COLUMN ai_model TEXT",
        "ALTER TABLE users ADD COLUMN allow_ai_history INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN display_name TEXT",
        "ALTER TABLE users ADD COLUMN pronouns TEXT",
        "ALTER TABLE users ADD COLUMN gender TEXT",
        "ALTER TABLE users ADD COLUMN custom_guidance TEXT",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        '''
        UPDATE users
        SET ai_tone = ?, ai_verbosity = ?, ai_focus = ?, ai_model = ?, allow_ai_history = 1,
            display_name = ?, pronouns = ?, gender = ?, custom_guidance = ?
        WHERE username = ?
        ''',
        (
            'analytical',
            'detailed',
            'practical-advice',
            'gpt-4.1',
            'Alex',
            'they/them',
            'non-binary',
            'Help me focus on evidence',
            'testuser',
        ),
    )
    conn.commit()
    conn.close()

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Preference-aware response',
        'tags': 'analysis',
        'people_names': '',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Current analysis text',
            'ai_style': 'creative',
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    analysis_options = mock_service.analyse_daily_entry.call_args.kwargs['analysis_options']
    related_context = mock_service.analyse_daily_entry.call_args.kwargs['related_context']
    attachment_context = mock_service.analyse_daily_entry.call_args.kwargs['attachment_context']
    assert analysis_options['ai_style'] == 'creative'
    assert analysis_options['ai_tone'] == 'analytical'
    assert analysis_options['ai_verbosity'] == 'detailed'
    assert analysis_options['ai_focus'] == 'practical-advice'
    assert analysis_options['ai_model'] == 'gpt-4.1'
    assert analysis_options['has_attachment_context'] is False
    assert related_context is None
    assert attachment_context is None
    assert 'Display name: Alex' in analysis_options['personal_context']
    assert 'Pronouns: they/them' in analysis_options['personal_context']
    assert 'Gender: non-binary' in analysis_options['personal_context']
    assert 'Custom guidance: Help me focus on evidence' in analysis_options['personal_context']


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_passes_recent_context_without_contract_change(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    """Analyse should pass bounded recent context to service without changing response shape."""
    token = get_auth_token(client)

    first_entry_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-28',
            'title': 'Earlier Alex entry',
            'user_message': 'Earlier daily entry about Alex at the library',
            'daily_people_names': 'Alex',
            'tags': 'reflection,friendship',
        }),
        content_type='application/json'
    )
    assert first_entry_response.status_code == 201

    second_entry_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-29',
            'title': 'Most recent Alex entry',
            'user_message': 'Most recent daily entry about Alex at the library',
            'daily_people_names': 'Alex',
            'tags': 'reflection,library',
        }),
        content_type='application/json'
    )
    assert second_entry_response.status_code == 201

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Context-aware response',
        'tags': 'context,analysis',
        'people_names': 'Alex',
        'places': 'Library',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'Current analysis text about Alex at the library'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert set(data.keys()) == {'ai_response', 'tags', 'daily_people_names', 'daily_places'}
    assert data['ai_response'] == 'Context-aware response'
    assert data['tags'] == 'context'
    assert data['daily_people_names'] == 'Alex'
    assert data['daily_places'] == 'Library'

    assert mock_service.analyse_daily_entry.call_args.args[0] == 'Current analysis text about Alex at the library'
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert 'Related entry memory:' in recent_context
    assert 'On 29 May 2026' in recent_context
    assert 'On 28 May 2026' in recent_context
    assert 'Most recent daily entry about Alex at the library' in recent_context
    assert 'Earlier daily entry about Alex at the library' in recent_context


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_can_use_completed_thought_record_context(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)
    import sqlite3

    conn = sqlite3.connect(os.environ['DB_PATH'])
    user_id = conn.execute(
        'SELECT id FROM users WHERE username = ?',
        ('testuser',),
    ).fetchone()[0]
    cursor = conn.execute(
        '''
        INSERT INTO cbt_worksheets (
            user_id, title, status, current_step, record_date, completed_at
        ) VALUES (?, ?, 'completed', 7, '2026-05-20', CURRENT_TIMESTAMP)
        ''',
        (user_id, 'Coffee plans with Katie'),
    )
    worksheet_id = int(cursor.lastrowid)
    conn.execute(
        '''
        INSERT INTO cbt_thought_record_data (
            worksheet_id, situation, unhelpful_thoughts, evidence_for,
            evidence_against, balanced_thought, next_step
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            worksheet_id,
            'Katie cancelled our coffee plans and I felt rejected.',
            'Katie does not value our friendship.',
            'The plans changed at short notice.',
            'Katie explained that she was unwell.',
            'A cancellation does not prove the friendship is unimportant.',
            'Wait and suggest another coffee date.',
        ),
    )
    conn.commit()
    conn.close()

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Context-aware response',
        'tags': 'reflection',
        'people_names': 'Katie',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post(
        '/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'mode': 'daily',
            'text': 'Katie changed our coffee plans again and I noticed the same rejection fear.',
            'reference_date': '2026-06-01',
        },
    )

    assert response.status_code == 200
    related_context = mock_service.analyse_daily_entry.call_args.kwargs['related_context']
    assert related_context is not None
    assert '[related 1 thought record]' in related_context
    assert 'Coffee plans with Katie' in related_context
    assert 'On 20 May 2026' in related_context


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_suppresses_history_when_user_setting_disabled(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)
    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    for statement in (
        "ALTER TABLE users ADD COLUMN ai_tone TEXT",
        "ALTER TABLE users ADD COLUMN ai_verbosity TEXT",
        "ALTER TABLE users ADD COLUMN ai_focus TEXT",
        "ALTER TABLE users ADD COLUMN ai_model TEXT",
        "ALTER TABLE users ADD COLUMN allow_ai_history INTEGER DEFAULT 1",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        '''
        UPDATE users
        SET allow_ai_history = 0
        WHERE username = ?
        ''',
        ('testuser',),
    )
    conn.commit()
    conn.close()

    client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2026-05-28', 'user_message': 'Earlier daily entry'}),
        content_type='application/json'
    )

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'History-off response',
        'tags': 'history,off',
        'people_names': '',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'Current analysis text'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    assert mock_service.analyse_daily_entry.call_args.kwargs['recent_context'] is None


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_success_keys_present(mock_openai, client):
    """Dream mode returns all expected structured keys."""
    token = get_auth_token(client)

    # Mock OpenAI response
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        'summary': 'I was flying over a city.',
        'interpretation': 'A desire for freedom and perspective.',
        'image_prompt': 'Surreal skyline beneath a moonlit sky',
        'tags': 'freedom,exploration',
        'people_names': 'Alex,hopefully,Sam',
        'places': 'City,Rooftop'
    })
    mock_client.chat.completions.create.return_value = mock_response

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'dream',
            'text': 'I dreamed I was flying above rooftops with Alex and Sam.'
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'summary' in data
    assert 'interpretation' in data


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_filters_generic_people_and_places(mock_openai, client):
    token = get_auth_token(client)

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        'summary': 'You were walking across a bridge with Maya.',
        'interpretation': 'The bridge suggests transition.',
        'image_prompt': 'Night bridge over dark water with distant lights',
        'tags': 'transition',
        'people_names': 'Maya,unknown,somebody',
        'places': 'Bridge,place,there'
    })
    mock_client.chat.completions.create.return_value = mock_response

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'dream',
            'text': 'I dreamed I was walking across a bridge with Maya.'
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['dream_people_names'] == 'Maya'
    assert data['dream_places'] == 'Bridge'
    assert 'image_prompt' in data
    assert 'tags' in data
    assert 'dream_people_names' in data
    assert 'dream_places' in data


@patch('routes.analyse.derive_dream_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_dream_entry_merges_user_and_ai_nltk_tags(
    mock_service_cls,
    mock_dream_nltk,
    client,
):
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service.analyse_dream_entry.return_value = {
        'summary': 'You were crossing a bridge with Maya.',
        'interpretation': 'The dream suggests transition and curiosity.',
        'image_prompt': 'Moonlit bridge over a river',
        'tags': 'transition,curiosity',
        'people_names': 'Maya',
        'places': 'Bridge',
    }
    mock_service_cls.return_value = mock_service
    mock_dream_nltk.side_effect = [
        {
            'tags': 'river,night',
            'dream_people_names': 'Jordan',
            'dream_places': 'Leeds',
        },
        {
            'tags': 'symbolism,transition',
            'dream_people_names': '',
            'dream_places': '',
        },
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'dream', 'text': 'I crossed a river at night with Jordan in Leeds'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['tags'] == 'river,night,transition,curiosity,symbolism'
    assert data['dream_people_names'] == 'Jordan,Maya'
    assert data['dream_places'] == 'Leeds,Bridge'


@patch('routes.analyse.derive_dream_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_dream_entry_filters_generic_ai_tags_from_merged_metadata(
    mock_service_cls,
    mock_dream_nltk,
    client,
):
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service.analyse_dream_entry.return_value = {
        'summary': 'You were crossing a bridge at night.',
        'interpretation': 'The bridge suggests transition and uncertainty.',
        'image_prompt': 'Night bridge over dark water with distant lights',
        'tags': 'dream,analysis,transition,night',
        'people_names': '',
        'places': 'Bridge',
    }
    mock_service_cls.return_value = mock_service
    mock_dream_nltk.side_effect = [
        {
            'tags': 'water',
            'dream_people_names': '',
            'dream_places': 'Leeds',
        },
        {
            'tags': 'entry,symbolism',
            'dream_people_names': '',
            'dream_places': '',
        },
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'dream', 'text': 'I was crossing a bridge at night over water.'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['tags'] == 'water,transition,night,symbolism'
    assert data['dream_places'] == 'Leeds,Bridge'


@patch('routes.analyse.OpenAIService', side_effect=Exception('boom'))
def test_analyse_returns_500_when_service_raises(_, client):
    """Unhandled analysis service exceptions map to a stable API error contract."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'A valid entry text'}),
        content_type='application/json'
    )

    assert response.status_code == 500
    data = json.loads(response.data)
    assert data == {'error': 'Analysis failed'}


@patch('routes.analyse.OpenAIService')
def test_analyse_returns_429_when_service_is_rate_limited(mock_service_cls, client):
    """Rate-limit and quota failures should surface as HTTP 429."""
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.side_effect = AnalysisRateLimitError('AI analysis rate-limited')
    mock_service_cls.return_value = mock_service

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'A valid entry text'}),
        content_type='application/json'
    )

    assert response.status_code == 429
    data = json.loads(response.data)
    assert data['code'] == 'rate_limited'
    assert 'rate-limited' in data['error']


@patch('services.openai_svc.OpenAI')
def test_analyse_accepts_text_at_exact_max_length(mock_openai, client):
    """Text exactly at ANALYSE_TEXT_MAX_LENGTH is accepted."""
    token = get_auth_token(client)

    # Mock OpenAI response
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        'ai_response': 'Length accepted',
        'tags': 'boundary,test',
        'people_names': '',
        'places': ''
    })
    mock_client.chat.completions.create.return_value = mock_response

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'a' * ANALYSE_TEXT_MAX_LENGTH
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'ai_response' in data


def test_analyse_rejects_missing_json_body(client):
    """Analyse endpoint requires JSON body object."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Request body must be a JSON object'


def test_analyse_rejects_non_string_text(client):
    """Analyse endpoint requires text to be a string."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 123}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Text must be a string'


def test_analyse_rejects_missing_text_key_for_daily_mode(client):
    """Analyse endpoint requires text key for daily mode payloads."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily'}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Text is required'


def test_analyse_rejects_whitespace_only_text(client):
    """Analyse endpoint rejects text that is only whitespace."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': '   \n\t  '}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Text is required'


def test_analyse_rejects_oversized_text(client):
    """Analyse endpoint enforces maximum text length."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'a' * (ANALYSE_TEXT_MAX_LENGTH + 1)}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == f'Text exceeds maximum length of {ANALYSE_TEXT_MAX_LENGTH} characters'


def test_analyse_rejects_invalid_mode(client):
    """Analyse endpoint only accepts daily or dream modes."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'weekly', 'text': 'Some text'}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Invalid mode. Use "daily" or "dream"'


def test_analyse_rate_limit_is_enforced(client, monkeypatch):
    monkeypatch.setenv('ANALYSE_RATE_LIMIT', '1 per minute')
    token = get_auth_token(client)
    headers = {'Authorization': f'Bearer {token}'}
    payload = {'mode': 'weekly', 'text': 'Some text'}

    first = client.post(
        '/api/analyse',
        headers=headers,
        data=json.dumps(payload),
        content_type='application/json',
    )
    second = client.post(
        '/api/analyse',
        headers=headers,
        data=json.dumps(payload),
        content_type='application/json',
    )

    assert first.status_code == 400
    assert second.status_code == 429
    assert json.loads(second.data)['error'] == 'Too many attempts. Try again shortly.'


def test_analyse_rejects_invalid_reference_date(client):
    """Analyse endpoint rejects malformed reference_date values."""
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'Valid text', 'reference_date': '31-05-2026'}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Invalid reference_date format. Use YYYY-MM-DD'


@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_accepts_valid_reference_date_without_contract_change(mock_service_cls, client):
    """Valid reference_date should not alter the daily analyse response contract."""
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Date-aware response',
        'tags': 'dated,analysis',
        'people_names': 'Alex',
        'places': 'Library',
    }
    mock_service_cls.return_value = mock_service

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Current analysis text',
            'reference_date': '2026-05-31',
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert set(data.keys()) == {'ai_response', 'tags', 'daily_people_names', 'daily_places'}
    assert data['ai_response'] == 'Date-aware response'


@patch('routes.analyse.OpenAIService')
def test_analyse_daily_recent_context_prefers_metadata_near_reference_date(mock_service_cls, client):
    """Related-entry memory should still use recency as a tie-breaker among similarly relevant entries."""
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service_cls.return_value = mock_service

    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Date-aware response',
        'tags': 'dated,analysis',
        'people_names': 'Alex',
        'places': 'Library',
    }

    for entry_date, title in [('2026-05-01', 'Older Alex entry'), ('2026-05-15', 'Nearer Alex entry')]:
        seed_response = client.post('/api/daily',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps({
                'entry_date': entry_date,
                'title': title,
                'user_message': f'{title} about Alex at the library',
                'daily_people_names': 'Alex',
                'tags': 'reflection,library',
            }),
            content_type='application/json'
        )
        assert seed_response.status_code == 201

    final_response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'target text about Alex at the library', 'reference_date': '2026-05-16'}),
        content_type='application/json'
    )

    assert final_response.status_code == 200
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert 'On 15 May 2026' in recent_context
    assert 'On 1 May 2026' in recent_context
    assert recent_context.find('On 15 May 2026') < recent_context.find('On 1 May 2026')


@patch('routes.analyse.OpenAIService')
def test_analyse_daily_recent_context_deduplicates_duplicate_metadata_headers(mock_service_cls, client):
    """Unrelated recent entries should not dominate related-entry memory."""
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service_cls.return_value = mock_service
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Final response',
        'tags': 'final',
        'people_names': '',
        'places': '',
    }

    related_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-10',
            'title': 'Alex library reflection',
            'user_message': 'A related entry about Alex and the library.',
            'daily_people_names': 'Alex',
            'tags': 'reflection,library',
        }),
        content_type='application/json'
    )
    assert related_response.status_code == 201

    unrelated_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-12',
            'title': 'Gym day',
            'user_message': 'An unrelated recent entry about the gym.',
            'daily_people_names': 'Tom',
            'tags': 'fitness,routine',
        }),
        content_type='application/json'
    )
    assert unrelated_response.status_code == 201

    final_response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'current text about Alex at the library', 'reference_date': '2026-05-13'}),
        content_type='application/json'
    )

    assert final_response.status_code == 200
    data = json.loads(final_response.data)
    assert set(data.keys()) == {'ai_response', 'tags', 'daily_people_names', 'daily_places'}

    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert 'Alex library reflection' in recent_context
    assert 'Gym day' not in recent_context


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_related_history_prefers_shared_people_and_theme_over_recency(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)

    older_related_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-06-05',
            'title': 'Katie uncertainty',
            'user_message': 'I felt upset after hearing from Katie again.',
            'tags': 'relationships,uncertainty',
            'daily_people_names': 'Katie',
        }),
        content_type='application/json'
    )
    assert older_related_response.status_code == 201

    recent_unrelated_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-06-11',
            'title': 'Gym routine',
            'user_message': 'I went to the gym and felt productive.',
            'tags': 'fitness,routine',
            'daily_people_names': 'Tom',
        }),
        content_type='application/json'
    )
    assert recent_unrelated_response.status_code == 201

    current_entry_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-06-12',
            'title': 'Thinking about Katie again',
            'user_message': 'I keep thinking about Katie and whether I should reach out.',
            'tags': 'relationships,reflection',
            'daily_people_names': 'Katie',
        }),
        content_type='application/json'
    )
    assert current_entry_response.status_code == 201
    current_entry_id = json.loads(current_entry_response.data)['id']

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Related-memory response',
        'tags': 'memory,analysis',
        'people_names': 'Katie',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'I keep thinking about Katie and whether I should reach out.',
            'entry_id': current_entry_id,
            'reference_date': '2026-06-12',
            'ai_style': 'reflective',
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert 'Related entry memory:' in recent_context
    assert 'On 5 June 2026' in recent_context
    assert 'shared theme: katie' in recent_context


@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_can_include_attachment_context(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-28',
            'title': 'Attachment context daily',
            'user_message': 'Daily content with reference material',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/daily/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'notes.pdf', 'application/pdf')},
        content_type='multipart/form-data'
    )
    attachment_id = json.loads(upload_response.data)['attachment']['id']

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    conn.execute(
        '''
        UPDATE entry_assets
        SET derived_text = ?, derived_text_source = ?
        WHERE id = ?
        ''',
        ('PDF summary about a difficult meeting', 'manual-note', attachment_id),
    )
    conn.commit()
    conn.close()

    mock_service = MagicMock()
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Attachment-aware response',
        'tags': 'attachment,analysis',
        'people_names': '',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Current analysis text',
            'entry_id': entry_id,
            'include_attachment_context': True,
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload['attachment_context_refs'] == ['notes.pdf (PDF text extracted)']
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    analysis_options = mock_service.analyse_daily_entry.call_args.kwargs['analysis_options']
    attachment_context = mock_service.analyse_daily_entry.call_args.kwargs['attachment_context']
    assert recent_context is not None
    assert analysis_options['has_attachment_context'] is True
    assert attachment_context is not None
    assert 'Attachment context:' in recent_context
    assert 'Your PDF attachment "notes.pdf"' in attachment_context
    assert 'Your PDF attachment "notes.pdf"' in recent_context
    assert 'PDF summary about a difficult meeting' in recent_context


def test_analyse_rejects_attachment_context_without_entry_id(client):
    token = get_auth_token(client)

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Current analysis text',
            'include_attachment_context': True,
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'entry_id is required when include_attachment_context is enabled'

def test_unauthorised_access(client):
    """Test accessing protected endpoint without token."""
    response = client.get('/api/daily')
    assert response.status_code == 401


def test_update_daily_entry_does_not_create_duplicate(client):
    """PUT /api/daily/:id must update in-place and never create a second row."""
    token = get_auth_token(client)

    # Create one entry
    create_resp = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-01', 'user_message': 'Original text'}),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    # Update it via PUT
    update_resp = client.put(f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'user_message': 'Updated text', 'title': 'Edited Title'}),
        content_type='application/json'
    )
    assert update_resp.status_code == 200

    # Confirm the total count is still 1
    list_resp = client.get('/api/daily',
        headers={'Authorization': f'Bearer {token}'}
    )
    entries = json.loads(list_resp.data)
    assert len(entries) == 1, 'PUT must not create a duplicate row'

    # Confirm the content was actually changed
    assert entries[0]['user_message'] == 'Updated text'
    assert entries[0]['title'] == 'Edited Title'


def test_analysis_attachment_refs_update_value_is_json_encoded():
    """Entry updates store attachment references as text, not raw Python lists."""
    from routes.entries import _normalise_update_field_value

    assert (
        _normalise_update_field_value(
            'analysis_attachment_refs',
            ['attachment-one.pdf', 'attachment-two.pdf'],
        )
        == '["attachment-one.pdf", "attachment-two.pdf"]'
    )
    assert _normalise_update_field_value('title', 'Keep text values') == 'Keep text values'


def test_update_daily_entry_not_found(client):
    """PUT for non-existent entry returns 404."""
    token = get_auth_token(client)
    response = client.put('/api/daily/999',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'user_message': 'Ghost entry'}),
        content_type='application/json'
    )
    assert response.status_code == 404


def test_update_dream_entry_does_not_create_duplicate(client):
    """PUT /api/dreams/:id must update in-place and never create a second row."""
    token = get_auth_token(client)

    # Create one dream entry
    create_resp = client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-02',
            'title': 'Flying Dream',
            'plot': 'I was flying over the city'
        }),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    # Update it via PUT
    update_resp = client.put(f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'plot': 'I was flying over mountains', 'interpretation': 'Freedom'}),
        content_type='application/json'
    )
    assert update_resp.status_code == 200

    # Confirm count is still 1
    list_resp = client.get('/api/dreams',
        headers={'Authorization': f'Bearer {token}'}
    )
    entries = json.loads(list_resp.data)
    assert len(entries) == 1, 'PUT must not create a duplicate dream row'

    # Confirm the content was updated
    assert entries[0]['plot'] == 'I was flying over mountains'
    assert entries[0]['interpretation'] == 'Freedom'


def test_update_dream_entry_not_found(client):
    """PUT for non-existent dream entry returns 404."""
    token = get_auth_token(client)
    response = client.put('/api/dreams/999',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'plot': 'Ghost dream'}),
        content_type='application/json'
    )
    assert response.status_code == 404


def test_update_daily_entry_updates_date_mood_and_ai_style(client):
    """PUT /api/daily/:id should accept date, mood and ai_style updates."""
    token = get_auth_token(client)

    create_resp = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-03',
            'entry_time': '09:10',
            'user_message': 'Original text',
            'mood': 'happy',
            'ai_style': 'friendly'
        }),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    # Move to a date where an entry already exists so numbering must increment.
    other_resp = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-04',
            'user_message': 'Existing target date entry'
        }),
        content_type='application/json'
    )
    assert other_resp.status_code == 201

    update_resp = client.put(f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-04',
            'entry_time': '17:45',
            'mood': 'thoughtful',
            'ai_style': 'reflective',
            'user_message': 'Updated text'
        }),
        content_type='application/json'
    )
    assert update_resp.status_code == 200

    list_resp = client.get('/api/daily', headers={'Authorization': f'Bearer {token}'})
    entries = json.loads(list_resp.data)
    updated = next(entry for entry in entries if entry['id'] == entry_id)

    assert updated['entry_date'] == '2024-03-04'
    assert updated['entry_time'] == '17:45'
    assert updated['mood'] == 'thoughtful'
    assert updated['ai_style'] == 'reflective'
    assert updated['entry_number'] == 2


@patch('routes.entries.derive_daily_nltk_fields')
def test_update_daily_entry_rebuilds_metadata_from_effective_state(mock_derive_daily, client):
    token = get_auth_token(client)
    mock_derive_daily.side_effect = [
        {
            'tags': 'focus',
            'daily_people_names': 'Alex',
            'daily_places': 'Office',
        },
        {
            'tags': 'focus,repair',
            'daily_people_names': 'Alex,Katie',
            'daily_places': 'Office',
        },
    ]

    create_resp = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-07',
            'title': 'Original title',
            'user_message': 'Met Alex at the office',
            'tags': 'manual',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'user_message': 'Met Alex and Katie at the office',
        }),
        content_type='application/json'
    )
    assert update_resp.status_code == 200

    detail_response = client.get(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    payload = json.loads(detail_response.data)

    assert payload['tags'] == 'manual,focus,repair'
    assert payload['daily_people_names'] == 'Alex,Katie'
    assert payload['daily_places'] == 'Office'


def test_update_dream_entry_updates_date_mood_and_ai_style(client):
    """PUT /api/dreams/:id should accept date, mood and ai_style updates."""
    token = get_auth_token(client)

    create_resp = client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-05',
            'entry_time': '07:15',
            'title': 'Original dream',
            'plot': 'I crossed a bridge',
            'mood': 'peaceful',
            'ai_style': 'creative'
        }),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    other_resp = client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-06',
            'title': 'Target date dream',
            'plot': 'Another dream'
        }),
        content_type='application/json'
    )
    assert other_resp.status_code == 201

    update_resp = client.put(f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-06',
            'entry_time': '22:05',
            'mood': 'anxious',
            'ai_style': 'brief',
            'plot': 'Updated dream plot'
        }),
        content_type='application/json'
    )
    assert update_resp.status_code == 200

    list_resp = client.get('/api/dreams', headers={'Authorization': f'Bearer {token}'})
    entries = json.loads(list_resp.data)
    updated = next(entry for entry in entries if entry['id'] == entry_id)

    assert updated['entry_date'] == '2024-03-06'
    assert updated['entry_time'] == '22:05'
    assert updated['mood'] == 'anxious'
    assert updated['ai_style'] == 'brief'
    assert updated['entry_number'] == 2


@patch('routes.entries.derive_dream_nltk_fields')
def test_update_dream_entry_rebuilds_metadata_from_effective_state(mock_derive_dream, client):
    token = get_auth_token(client)
    mock_derive_dream.side_effect = [
        {
            'tags': 'water,night',
            'dream_people_names': 'Jordan',
            'dream_places': 'Lake',
        },
        {
            'tags': 'water,night,storm',
            'dream_people_names': 'Jordan,Maya',
            'dream_places': 'Lake',
        },
    ]

    create_resp = client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-11',
            'title': 'Original dream',
            'plot': 'Jordan by the lake',
            'tags': 'manual',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'plot': 'Jordan and Maya near the lake in a storm',
        }),
        content_type='application/json'
    )
    assert update_resp.status_code == 200

    detail_response = client.get(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    payload = json.loads(detail_response.data)

    assert payload['tags'] == 'manual,water,night,storm'
    assert payload['dream_people_names'] == 'Jordan,Maya'
    assert payload['dream_places'] == 'Lake'


def test_update_daily_entry_rejects_invalid_entry_date(client):
    """PUT /api/daily/:id should return 400 for invalid date format."""
    token = get_auth_token(client)

    create_resp = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-07', 'user_message': 'Valid entry'}),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '07/03/2024'}),
        content_type='application/json'
    )

    assert update_resp.status_code == 400
    data = json.loads(update_resp.data)
    assert data['error'] == 'Invalid entry_date format. Use YYYY-MM-DD'

def test_update_daily_entry_rejects_future_entry_date(client):
    """PUT /api/daily/:id should reject future dates."""
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024-03-07', 'user_message': 'Valid entry'}),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2999-01-01'}),
        content_type='application/json'
    )

    assert update_resp.status_code == 400
    data = json.loads(update_resp.data)
    assert data['error'] == 'Future entry dates are not allowed'


def test_update_dream_entry_rejects_invalid_entry_date(client):
    """PUT /api/dreams/:id should return 400 for invalid date format."""
    token = get_auth_token(client)

    create_resp = client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-08',
            'title': 'Valid dream',
            'plot': 'Valid plot'
        }),
        content_type='application/json'
    )
    assert create_resp.status_code == 201
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2024/03/08'}),
        content_type='application/json'
    )

    assert update_resp.status_code == 400
    data = json.loads(update_resp.data)
    assert data['error'] == 'Invalid entry_date format. Use YYYY-MM-DD'

def test_create_dream_entry_rejects_future_date(client):
    """POST /api/dreams should reject future dates."""
    token = get_auth_token(client)

    response = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2999-01-01',
            'title': 'Future dream',
            'plot': 'Dream text'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Future entry dates are not allowed'


def test_create_dream_entry_persists_mood_and_ai_style(client):
    """POST /api/dreams should persist mood and ai_style on initial save."""
    token = get_auth_token(client)

    create_response = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-09',
            'entry_time': '07:45',
            'title': 'Persist mood dream',
            'plot': 'A dream for persistence checks',
            'mood': 'peaceful',
            'ai_style': 'creative',
        }),
        content_type='application/json',
    )

    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    detail_response = client.get(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert detail_response.status_code == 200
    payload = json.loads(detail_response.data)
    assert payload['mood'] == 'peaceful'
    assert payload['ai_style'] == 'creative'


@patch('routes.entries.derive_dream_nltk_fields')
def test_create_dream_entry_merges_nltk_enrichment_on_save(mock_derive_dream, client):
    token = get_auth_token(client)
    mock_derive_dream.return_value = {
        'tags': 'school,flight',
        'dream_people_names': 'Jordan',
        'dream_places': 'Old school',
    }

    create_response = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-10',
            'title': 'Dream',
            'plot': 'Back at school with Jordan',
            'tags': 'manual',
            'dream_people_names': 'Maya',
            'dream_places': 'Garden',
        }),
        content_type='application/json',
    )

    assert create_response.status_code == 201
    entry_id = json.loads(create_response.data)['id']

    detail_response = client.get(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    payload = json.loads(detail_response.data)

    assert payload['tags'] == 'manual,school,flight'
    assert payload['dream_people_names'] == 'Maya,Jordan'
    assert payload['dream_places'] == 'Garden,Old school'

def test_update_dream_entry_rejects_future_entry_date(client):
    """PUT /api/dreams/:id should reject future dates."""
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-08',
            'title': 'Dream',
            'plot': 'Valid dream'
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2999-01-01'}),
        content_type='application/json'
    )

    assert update_resp.status_code == 400
    data = json.loads(update_resp.data)
    assert data['error'] == 'Future entry dates are not allowed'


@patch('routes.entries.OpenAIService')
def test_generate_dream_image_updates_entry(mock_service_cls, client):
    token = get_auth_token(client)
    grant_ai_media_access()

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-10',
            'title': 'Moon dream',
            'plot': 'I saw a silver moon over a lake',
            'image_prompt': 'Moonlit lake with silver reflections',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_prompt': 'Moonlit lake with silver reflections'}),
        content_type='application/json'
    )

    mock_service = MagicMock()
    mock_service.generate_image.return_value = create_test_image_bytes(
        size=(933, 705),
        color=(10, 20, 30),
        format_name='PNG',
    )
    mock_service_cls.return_value = mock_service

    response = client.post(
        f'/api/dreams/{entry_id}/generate-image',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == 'Moonlit lake with silver reflections'
    assert data['image_url'].startswith('http://localhost/media/')
    assert data['image_source'] == 'ai'
    assert data['image_position_x'] == 50.0
    assert data['image_position_y'] == 50.0

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_url, image_storage_key, image_source FROM dreamdiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] is None
    assert isinstance(row[1], str) and row[1].startswith('entries/dream/')
    assert row[2] == 'ai'
    assert os.path.exists(os.path.join(os.environ['MEDIA_ROOT'], row[1]))


@patch('routes.entries.OpenAIService')
def test_generate_dream_image_uses_override_without_persisting_it(mock_service_cls, client):
    token = get_auth_token(client)
    grant_ai_media_access()

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-12',
            'title': 'Edited prompt dream',
            'plot': 'I was under a green sky',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_prompt': 'Original stored prompt'}),
        content_type='application/json'
    )

    mock_service = MagicMock()
    mock_service.generate_image.return_value = create_test_image_bytes(
        size=(933, 705),
        color=(30, 40, 50),
        format_name='PNG',
    )
    mock_service_cls.return_value = mock_service

    response = client.post(
        f'/api/dreams/{entry_id}/generate-image',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_prompt_override': 'Temporary edited prompt'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == 'Temporary edited prompt'
    assert data['image_url'].startswith('http://localhost/media/')
    mock_service.generate_image.assert_called_once_with('Temporary edited prompt')

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_url, image_storage_key FROM dreamdiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] == 'Original stored prompt'
    assert row[1] is None
    assert isinstance(row[2], str) and row[2].startswith('entries/dream/')


def test_generate_dream_image_rejects_missing_prompt(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-11',
            'title': 'Promptless dream',
            'plot': 'I was walking through fog'
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    response = client.post(
        f'/api/dreams/{entry_id}/generate-image',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'This dream entry does not yet have an image prompt.'


def test_generate_dream_image_not_found(client):
    token = get_auth_token(client)

    response = client.post(
        '/api/dreams/999/generate-image',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({}),
        content_type='application/json'
    )

    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['error'] == 'Entry not found'


def test_upload_dream_image_updates_entry(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-12',
            'title': 'Uploadable dream',
            'plot': 'Dream text',
            'image_prompt': 'Moonlit hills'
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_prompt': 'Moonlit hills'}),
        content_type='application/json'
    )

    image_bytes = create_test_image_bytes(size=(800, 1600))

    response = client.post(
        f'/api/dreams/{entry_id}/image',
        headers={'Authorization': f'Bearer {token}'},
        data={'image': (BytesIO(image_bytes), 'dream.png')},
        content_type='multipart/form-data'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == ''
    assert data['recycled_image_prompt'] == 'Moonlit hills'
    assert data['image_url'].startswith('http://localhost/media/')
    assert data['image_source'] == 'upload'
    assert data['image_position_x'] == 50.0
    assert data['image_position_y'] == 50.0

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_url, image_storage_key, image_source FROM dreamdiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] is None
    assert row[1] is None
    assert isinstance(row[2], str) and row[2].startswith('entries/dream/')
    assert row[3] == 'upload'
    image = Image.open(os.path.join(os.environ['MEDIA_ROOT'], row[2]))
    assert image.height == 705
    assert image.width < image.height
    assert image.width <= 933


def test_upload_dream_image_rejects_invalid_type(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-13',
            'title': 'Invalid upload dream',
            'plot': 'Dream text',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    response = client.post(
        f'/api/dreams/{entry_id}/image',
        headers={'Authorization': f'Bearer {token}'},
        data={'image': (BytesIO(b'not an image'), 'dream.txt', 'text/plain')},
        content_type='multipart/form-data'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Unsupported image type. Use JPG, PNG, or WEBP.'


def test_delete_dream_image_clears_only_image(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-14',
            'title': 'Delete image dream',
            'plot': 'Dream text',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'image_prompt': 'Keep this prompt',
            'image_storage_key': None,
            'image_url': 'data:image/png;base64,abc123',
            'image_position_x': 20,
            'image_position_y': 80,
        }),
        content_type='application/json'
    )

    response = client.delete(
        f'/api/dreams/{entry_id}/image',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == 'Keep this prompt'
    assert data['image_url'] is None
    assert data['image_position_x'] == 50.0
    assert data['image_position_y'] == 50.0

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_url, image_storage_key, image_position_x, image_position_y FROM dreamdiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] == 'Keep this prompt'
    assert row[1] is None
    assert row[2] is None
    assert row[3] == 50.0
    assert row[4] == 50.0


@patch('routes.entries.OpenAIService')
def test_generate_daily_image_derives_prompt_and_stores_image(mock_service_cls, client):
    token = get_auth_token(client)
    grant_ai_media_access()

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-17',
            'title': 'Park walk',
            'user_message': 'I went for a thoughtful walk through the park after work.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'ai_response': 'You seemed calm and reflective, finding a quiet reset in nature.'}),
        content_type='application/json'
    )

    mock_service = MagicMock()
    mock_service.generate_image.return_value = create_test_image_bytes(
        size=(933, 705),
        color=(90, 120, 150),
        format_name='PNG',
    )
    mock_service_cls.return_value = mock_service

    response = client.post(
        f'/api/daily/{entry_id}/generate-image',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_url'].startswith('http://localhost/media/')
    assert 'Park walk' in data['image_prompt']
    assert 'Do not render any visible text' in data['image_prompt']
    assert 'anonymous' in data['image_prompt'].lower()
    assert 'Source context:' not in data['image_prompt']
    assert data['image_source'] == 'ai'
    assert data['image_position_x'] == 50.0
    assert data['image_position_y'] == 50.0

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_url, image_storage_key FROM dailydiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert isinstance(row[0], str) and 'Park walk' in row[0]
    assert 'Title:' not in row[0]
    assert row[1] is None
    assert isinstance(row[2], str) and row[2].startswith('entries/daily/')


@patch('routes.entries.OpenAIService')
def test_generate_daily_image_override_does_not_persist_it(mock_service_cls, client):
    token = get_auth_token(client)
    grant_ai_media_access()

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-18',
            'title': 'Original day',
            'user_message': 'I had a difficult but meaningful conversation.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'ai_response': 'You were brave enough to have an honest conversation.',
            'image_prompt': 'Original stored daily prompt',
        }),
        content_type='application/json'
    )

    mock_service = MagicMock()
    mock_service.generate_image.return_value = create_test_image_bytes(
        size=(933, 705),
        color=(50, 70, 90),
        format_name='PNG',
    )
    mock_service_cls.return_value = mock_service

    response = client.post(
        f'/api/daily/{entry_id}/generate-image',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_prompt_override': 'Temporary daily prompt override'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == 'Temporary daily prompt override'

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_storage_key FROM dailydiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] == 'Original stored daily prompt'
    assert isinstance(row[1], str) and row[1].startswith('entries/daily/')


def test_upload_daily_image_updates_entry(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-19',
            'title': 'Upload daily',
            'user_message': 'Daily content',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_prompt': 'Daily prompt to recycle'}),
        content_type='application/json'
    )

    response = client.post(
        f'/api/daily/{entry_id}/image',
        headers={'Authorization': f'Bearer {token}'},
        data={'image': (BytesIO(create_test_image_bytes(size=(1600, 800))), 'daily.png')},
        content_type='multipart/form-data'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == ''
    assert data['recycled_image_prompt'] == 'Daily prompt to recycle'
    assert data['image_url'].startswith('http://localhost/media/')
    assert data['image_source'] == 'upload'

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_url, image_storage_key, image_source FROM dailydiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] is None
    assert row[1] is None
    assert isinstance(row[2], str) and row[2].startswith('entries/daily/')
    assert row[3] == 'upload'
    image = Image.open(os.path.join(os.environ['MEDIA_ROOT'], row[2]))
    assert image.width == 933
    assert image.height < image.width
    assert image.height <= 705


def test_delete_daily_image_clears_only_image(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-20',
            'title': 'Delete daily image',
            'user_message': 'Daily content',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    client.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'image_prompt': 'Keep daily prompt',
            'image_url': 'data:image/png;base64,abc123',
            'image_position_x': 12,
            'image_position_y': 72,
        }),
        content_type='application/json'
    )

    response = client.delete(
        f'/api/daily/{entry_id}/image',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_prompt'] == 'Keep daily prompt'
    assert data['image_url'] is None
    assert data['image_position_x'] == 50.0
    assert data['image_position_y'] == 50.0

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_prompt, image_url, image_storage_key, image_position_x, image_position_y FROM dailydiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] == 'Keep daily prompt'
    assert row[1] is None
    assert row[2] is None
    assert row[3] == 50.0
    assert row[4] == 50.0


@patch('routes.entries.extract_pdf_attachment_content')
def test_upload_daily_attachment_is_serialised_on_entry_detail(
    mock_extract_pdf_attachment_content,
    client,
):
    token = get_auth_token(client)
    mock_extract_pdf_attachment_content.return_value = (
        'Meeting notes about feeling uncertain after the conversation.',
        'pdf-text-extraction',
    )

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-21',
            'title': 'Attachment daily',
            'user_message': 'Daily content with attachment',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/daily/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'notes.pdf', 'application/pdf')},
        content_type='multipart/form-data'
    )

    assert upload_response.status_code == 201
    attachment = json.loads(upload_response.data)['attachment']
    assert attachment['original_filename'] == 'notes.pdf'
    assert attachment['mime_type'] == 'application/pdf'
    assert attachment['is_pdf'] is True
    assert attachment['derived_text'] == (
        'Meeting notes about feeling uncertain after the conversation.'
    )
    assert attachment['derived_text_source'] == 'pdf-text-extraction'
    assert attachment['has_derived_text'] is True
    assert attachment['url'].startswith('http://localhost/media/')

    detail_response = client.get(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert detail_response.status_code == 200
    detail_data = json.loads(detail_response.data)
    assert len(detail_data['attachments']) == 1
    assert detail_data['attachments'][0]['original_filename'] == 'notes.pdf'
    assert detail_data['attachments'][0]['derived_text_source'] == 'pdf-text-extraction'


@patch('routes.entries.OpenAIService')
@patch('routes.entries.extract_pdf_attachment_content')
def test_upload_daily_pdf_attachment_cleans_ocr_text_before_persisting(
    mock_extract_pdf_attachment_content,
    mock_openai_service_cls,
    client,
):
    token = get_auth_token(client)
    mock_extract_pdf_attachment_content.return_value = (
        "‘Strong. commived, restive? (tos) fun ooking bear saricu",
        'pdf-ocr',
    )
    mock_service = MagicMock()
    mock_service.clean_ocr_extracted_text.return_value = (
        'Strong, committed, creative. Fun-looking and serious.'
    )
    mock_openai_service_cls.return_value = mock_service

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-21',
            'title': 'OCR attachment daily',
            'user_message': 'Daily content with OCR attachment',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/daily/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'survey.pdf', 'application/pdf')},
        content_type='multipart/form-data'
    )

    assert upload_response.status_code == 201
    attachment = json.loads(upload_response.data)['attachment']
    assert attachment['derived_text'] == 'Strong, committed, creative. Fun-looking and serious.'
    assert attachment['derived_text_source'] == 'pdf-ocr'
    mock_service.clean_ocr_extracted_text.assert_called_once()


@patch('routes.entries.OpenAIService')
@patch('routes.entries.extract_pdf_attachment_content')
def test_derive_daily_pdf_attachment_text_refreshes_saved_text(
    mock_extract_pdf_attachment_content,
    mock_openai_service_cls,
    client,
):
    token = get_auth_token(client)
    mock_extract_pdf_attachment_content.return_value = (
        "‘Strong. commived, restive? (tos) fun ooking bear saricu",
        'pdf-ocr',
    )
    mock_service = MagicMock()
    mock_service.clean_ocr_extracted_text.return_value = (
        'Strong, committed, creative. Fun-looking and serious.'
    )
    mock_openai_service_cls.return_value = mock_service

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-21',
            'title': 'Refresh OCR attachment daily',
            'user_message': 'Daily content with OCR attachment',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    with patch('routes.entries.extract_pdf_attachment_content', return_value=(None, None)):
        upload_response = client.post(
            f'/api/daily/{entry_id}/attachments',
            headers={'Authorization': f'Bearer {token}'},
            data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'survey.pdf', 'application/pdf')},
            content_type='multipart/form-data'
        )
    assert upload_response.status_code == 201
    attachment_id = json.loads(upload_response.data)['attachment']['id']

    refresh_response = client.post(
        f'/api/daily/{entry_id}/attachments/{attachment_id}/derive-text',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert refresh_response.status_code == 200
    attachment = json.loads(refresh_response.data)['attachment']
    assert attachment['derived_text'] == 'Strong, committed, creative. Fun-looking and serious.'
    assert attachment['derived_text_source'] == 'pdf-ocr'


@patch('routes.analyse.extract_pdf_attachment_content')
@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_refreshes_low_quality_saved_pdf_ocr_text(
    mock_service_cls,
    mock_daily_nltk,
    mock_extract_pdf_attachment_content,
    client,
):
    token = get_auth_token(client)
    mock_extract_pdf_attachment_content.return_value = (
        'Strong committed creative and confident with a serious presence.',
        'pdf-ocr',
    )

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-29',
            'title': 'Low-quality OCR entry',
            'user_message': 'Daily entry with a noisy OCR attachment.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    with patch('routes.entries.extract_pdf_attachment_content', return_value=(
        'Strong. commived, restive? (tos) fun ooking bear saricu',
        'pdf-ocr',
    )), patch('routes.entries.OpenAIService') as mock_upload_openai_cls:
        mock_upload_service = MagicMock()
        mock_upload_service.clean_ocr_extracted_text.return_value = (
            'Strong. commived, restive? (tos) fun ooking bear saricu'
        )
        mock_upload_openai_cls.return_value = mock_upload_service
        upload_response = client.post(
            f'/api/daily/{entry_id}/attachments',
            headers={'Authorization': f'Bearer {token}'},
            data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'older-notes.pdf', 'application/pdf')},
            content_type='multipart/form-data'
        )
    assert upload_response.status_code == 201
    attachment_id = json.loads(upload_response.data)['attachment']['id']

    mock_service = MagicMock()
    mock_service.clean_ocr_extracted_text.return_value = (
        'Strong committed creative and confident with a serious presence.'
    )
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Attachment-aware response',
        'tags': 'attachment,analysis',
        'people_names': '',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Current analysis text',
            'entry_id': entry_id,
            'include_attachment_context': True,
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert 'Strong committed creative and confident with a serious presence.' in recent_context

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT derived_text, derived_text_source FROM entry_assets WHERE id = ?',
        (attachment_id,),
    ).fetchone()
    conn.close()
    assert row == (
        'Strong committed creative and confident with a serious presence.',
        'pdf-ocr',
    )


def test_delete_dream_attachment_removes_stored_file(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-22',
            'title': 'Attachment dream',
            'plot': 'A dream with a recording.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/dreams/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={'attachment': (BytesIO(b'ID3 pretend mp3 bytes'), 'voice-note.mp3', 'audio/mpeg')},
        content_type='multipart/form-data'
    )
    assert upload_response.status_code == 201
    attachment = json.loads(upload_response.data)['attachment']

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT storage_key FROM entry_assets WHERE id = ?',
        (attachment['id'],),
    ).fetchone()
    conn.close()
    assert row and os.path.exists(os.path.join(os.environ['MEDIA_ROOT'], row[0]))

    delete_response = client.delete(
        f'/api/dreams/{entry_id}/attachments/{attachment["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert delete_response.status_code == 200

    conn = sqlite3.connect(os.environ['DB_PATH'])
    deleted_row = conn.execute(
        'SELECT storage_key FROM entry_assets WHERE id = ?',
        (attachment['id'],),
    ).fetchone()
    conn.close()
    assert deleted_row is None
    assert not os.path.exists(os.path.join(os.environ['MEDIA_ROOT'], row[0]))


def test_attachment_limit_rejects_fourth_file(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-23',
            'title': 'Attachment limit',
            'user_message': 'Testing attachment limit',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    for file_number in range(3):
        upload_response = client.post(
            f'/api/daily/{entry_id}/attachments',
            headers={'Authorization': f'Bearer {token}'},
            data={
                'attachment': (
                    BytesIO(f'%PDF-1.4 file {file_number}'.encode('utf-8')),
                    f'notes-{file_number}.pdf',
                    'application/pdf',
                )
            },
            content_type='multipart/form-data'
        )
        assert upload_response.status_code == 201

    fourth_response = client.post(
        f'/api/daily/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={
            'attachment': (
                BytesIO(b'%PDF-1.4 overflow'),
                'overflow.pdf',
                'application/pdf',
            )
        },
        content_type='multipart/form-data'
    )

    assert fourth_response.status_code == 400
    payload = json.loads(fourth_response.data)
    assert 'up to 3 attachments' in payload['error']


def test_attachment_download_uses_attachment_headers(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-24',
            'title': 'Attachment download',
            'plot': 'Dream attachment download.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/dreams/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={
            'attachment': (
                BytesIO(b'ID3 pretend mp3 bytes'),
                'voice-note.mp3',
                'audio/mpeg',
            )
        },
        content_type='multipart/form-data'
    )
    attachment = json.loads(upload_response.data)['attachment']

    download_response = client.get(
        f'/api/dreams/{entry_id}/attachments/{attachment["id"]}/download',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert download_response.status_code == 200
    assert download_response.headers['Content-Type'] == 'audio/mpeg'
    assert 'attachment;' in download_response.headers['Content-Disposition']
    assert 'voice-note.mp3' in download_response.headers['Content-Disposition']
    assert download_response.data == b'ID3 pretend mp3 bytes'


@patch('routes.entries.OpenAIService')
def test_transcribe_dream_audio_attachment_persists_derived_text(mock_openai_service_cls, client):
    token = get_auth_token(client)
    grant_ai_media_access()

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-25',
            'title': 'Attachment transcription',
            'plot': 'Dream attachment transcription.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/dreams/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={
            'attachment': (
                BytesIO(b'ID3 pretend mp3 bytes'),
                'voice-note.mp3',
                'audio/mpeg',
            )
        },
        content_type='multipart/form-data'
    )
    attachment = json.loads(upload_response.data)['attachment']

    mock_service = MagicMock()
    mock_service.transcribe_audio_attachment.return_value = 'Transcript text from audio'
    mock_openai_service_cls.return_value = mock_service

    transcribe_response = client.post(
        f'/api/dreams/{entry_id}/attachments/{attachment["id"]}/transcribe',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert transcribe_response.status_code == 200
    payload = json.loads(transcribe_response.data)
    assert payload['attachment']['derived_text'] == 'Transcript text from audio'
    assert payload['attachment']['derived_text_source'] == 'audio-transcription'
    assert payload['attachment']['has_derived_text'] is True

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT derived_text, derived_text_source FROM entry_assets WHERE id = ?',
        (attachment['id'],),
    ).fetchone()
    conn.close()
    assert row == ('Transcript text from audio', 'audio-transcription')


def test_transcribe_attachment_rejects_non_audio_file(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-26',
            'title': 'PDF only',
            'user_message': 'Daily content with pdf attachment',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    upload_response = client.post(
        f'/api/daily/{entry_id}/attachments',
        headers={'Authorization': f'Bearer {token}'},
        data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'notes.pdf', 'application/pdf')},
        content_type='multipart/form-data'
    )
    attachment = json.loads(upload_response.data)['attachment']

    response = client.post(
        f'/api/daily/{entry_id}/attachments/{attachment["id"]}/transcribe',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 400
    payload = json.loads(response.data)
    assert payload['error'] == 'Only audio attachments can be transcribed.'


@patch('routes.analyse.extract_pdf_attachment_content')
@patch('routes.analyse.derive_daily_nltk_fields')
@patch('routes.analyse.OpenAIService')
def test_analyse_daily_entry_lazily_extracts_pdf_text_for_older_attachment(
    mock_service_cls,
    mock_daily_nltk,
    mock_extract_pdf_attachment_content,
    client,
):
    token = get_auth_token(client)
    mock_extract_pdf_attachment_content.return_value = (
        'Recovered PDF text about an old difficult meeting and next steps.',
        'pdf-ocr',
    )

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-29',
            'title': 'Older PDF entry',
            'user_message': 'Daily entry with an older PDF attachment.',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    with patch('routes.entries.extract_pdf_attachment_content', return_value=(None, None)):
        upload_response = client.post(
            f'/api/daily/{entry_id}/attachments',
            headers={'Authorization': f'Bearer {token}'},
            data={'attachment': (BytesIO(b'%PDF-1.4 sample pdf bytes'), 'older-notes.pdf', 'application/pdf')},
            content_type='multipart/form-data'
        )
    assert upload_response.status_code == 201
    attachment_id = json.loads(upload_response.data)['attachment']['id']

    mock_service = MagicMock()
    mock_service.clean_ocr_extracted_text.return_value = (
        'Recovered PDF text about an old difficult meeting and next steps.'
    )
    mock_service.analyse_daily_entry.return_value = {
        'ai_response': 'Attachment-aware response',
        'tags': 'attachment,analysis',
        'people_names': '',
        'places': '',
    }
    mock_service_cls.return_value = mock_service
    mock_daily_nltk.side_effect = [
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
        {'tags': '', 'daily_people_names': '', 'daily_places': ''},
    ]

    response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'mode': 'daily',
            'text': 'Current analysis text',
            'entry_id': entry_id,
            'include_attachment_context': True,
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload['attachment_context_refs'] == ['older-notes.pdf (PDF OCR text)']
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    analysis_options = mock_service.analyse_daily_entry.call_args.kwargs['analysis_options']
    attachment_context = mock_service.analyse_daily_entry.call_args.kwargs['attachment_context']
    assert recent_context is not None
    assert analysis_options['has_attachment_context'] is True
    assert attachment_context is not None
    assert 'Your PDF attachment "older-notes.pdf"' in attachment_context
    assert 'Your PDF attachment "older-notes.pdf"' in recent_context
    assert 'Recovered PDF text about an old difficult meeting and next steps.' in recent_context

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT derived_text, derived_text_source FROM entry_assets WHERE id = ?',
        (attachment_id,),
    ).fetchone()
    conn.close()
    assert row == (
        'Recovered PDF text about an old difficult meeting and next steps.',
        'pdf-ocr',
    )


def test_update_daily_image_position_persists(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-21',
            'title': 'Position daily',
            'user_message': 'Daily content',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'image_position_x': 22,
            'image_position_y': 64,
        }),
        content_type='application/json'
    )

    assert update_resp.status_code == 200

    get_resp = client.get(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert get_resp.status_code == 200
    data = json.loads(get_resp.data)
    assert data['image_position_x'] == 22.0
    assert data['image_position_y'] == 64.0


def test_get_dream_entry_lazily_migrates_legacy_image_data_url(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-15',
            'title': 'Legacy image dream',
            'plot': 'Dream text',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    legacy_image = f"data:image/png;base64,{base64.b64encode(create_test_image_bytes(format_name='PNG')).decode('ascii')}"
    client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'image_url': legacy_image}),
        content_type='application/json'
    )

    response = client.get(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['image_url'].startswith('http://localhost/media/')

    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    row = conn.execute(
        'SELECT image_url, image_storage_key FROM dreamdiary_entries WHERE id = ?',
        (entry_id,),
    ).fetchone()
    conn.close()
    assert row[0] is None
    assert isinstance(row[1], str) and row[1].startswith('entries/dream/')
    assert os.path.exists(os.path.join(os.environ['MEDIA_ROOT'], row[1]))


def test_update_dream_image_position_persists(client):
    token = get_auth_token(client)

    create_resp = client.post(
        '/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-03-16',
            'title': 'Positioned dream',
            'plot': 'Dream text',
        }),
        content_type='application/json'
    )
    entry_id = json.loads(create_resp.data)['id']

    update_resp = client.put(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'image_position_x': 18,
            'image_position_y': 76,
        }),
        content_type='application/json'
    )

    assert update_resp.status_code == 200

    get_resp = client.get(
        f'/api/dreams/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert get_resp.status_code == 200
    data = json.loads(get_resp.data)
    assert data['image_position_x'] == 18.0
    assert data['image_position_y'] == 76.0

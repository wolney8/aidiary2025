# server/tests/test_entries.py
# Entries CRUD tests
import pytest
import json
from app import create_app
import tempfile
import os
import shutil
import base64
from io import BytesIO
from unittest.mock import patch, MagicMock
from routes.analyse import ANALYSE_TEXT_MAX_LENGTH
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
    client.post('/api/dreams',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2026-05-03',
            'title': 'Dream seed',
            'plot': 'Dream bulk delete seed'
        }),
        content_type='application/json'
    )

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
    assert data['last_entry_date'] == '2026-05-03'


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
        '/api/import/export?from_date=2026-05-01&to_date=2026-05-03&include_daily=true&include_dreams=true',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert export_response.status_code == 200
    guard_token = export_response.headers.get('X-AiDiary-Export-Token')
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
    assert delete_data['deleted_total'] == 2
    assert delete_data['deleted_daily'] == 1
    assert delete_data['deleted_dreams'] == 1

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
def test_analyse_daily_entry_passes_recent_context_without_contract_change(
    mock_service_cls,
    mock_daily_nltk,
    client,
):
    """Analyse should pass bounded recent context to service without changing response shape."""
    token = get_auth_token(client)

    first_entry_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2026-05-28', 'user_message': 'Earlier daily entry'}),
        content_type='application/json'
    )
    assert first_entry_response.status_code == 201

    second_entry_response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'entry_date': '2026-05-29', 'user_message': 'Most recent daily entry'}),
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
        data=json.dumps({'mode': 'daily', 'text': 'Current analysis text'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert set(data.keys()) == {'ai_response', 'tags', 'daily_people_names', 'daily_places'}
    assert data['ai_response'] == 'Context-aware response'
    assert data['tags'] == 'context,analysis'
    assert data['daily_people_names'] == 'Alex'
    assert data['daily_places'] == 'Library'

    assert mock_service.analyse_daily_entry.call_args.args[0] == 'Current analysis text'
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert 'Most recent daily entry' in recent_context
    assert 'Earlier daily entry' in recent_context


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
    assert 'image_prompt' in data
    assert 'tags' in data
    assert 'dream_people_names' in data
    assert 'dream_places' in data
    assert data['dream_people_names'] == 'Alex,Sam'


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
    """Metadata-backed recent context should prioritise rows nearest to reference_date."""
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service_cls.return_value = mock_service

    def _daily_payload(label: str) -> dict:
        return {
            'ai_response': f'Header {label}',
            'tags': f'tag-{label}',
            'people_names': '',
            'places': '',
        }

    mock_service.analyse_daily_entry.side_effect = [
        _daily_payload('old'),
        _daily_payload('near'),
        _daily_payload('far_future'),
        _daily_payload('final'),
    ]

    seed_payloads = [
        ('2026-05-01', 'seed old'),
        ('2026-05-15', 'seed near'),
        ('2026-05-30', 'seed far future'),
    ]
    for reference_date, text in seed_payloads:
        seed_response = client.post('/api/analyse',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps({'mode': 'daily', 'text': text, 'reference_date': reference_date}),
            content_type='application/json'
        )
        assert seed_response.status_code == 200

    final_response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'target text', 'reference_date': '2026-05-16'}),
        content_type='application/json'
    )

    assert final_response.status_code == 200
    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert 'ref_date=2026-05-15' in recent_context
    assert recent_context.find('ref_date=2026-05-15') < recent_context.find('ref_date=2026-05-30')


@patch('routes.analyse.OpenAIService')
def test_analyse_daily_recent_context_deduplicates_duplicate_metadata_headers(mock_service_cls, client):
    """Duplicate metadata summary headers should not dominate recent context."""
    token = get_auth_token(client)

    mock_service = MagicMock()
    mock_service_cls.return_value = mock_service
    mock_service.analyse_daily_entry.side_effect = [
        {
            'ai_response': 'Repeated metadata header',
            'tags': 'repeat,stable',
            'people_names': 'Alex',
            'places': 'Library',
        },
        {
            'ai_response': 'Repeated metadata header',
            'tags': 'repeat,stable',
            'people_names': 'Alex',
            'places': 'Library',
        },
        {
            'ai_response': 'Distinct metadata header',
            'tags': 'distinct',
            'people_names': '',
            'places': '',
        },
        {
            'ai_response': 'Final response',
            'tags': 'final',
            'people_names': '',
            'places': '',
        },
    ]

    for reference_date in ['2026-05-10', '2026-05-11', '2026-05-12']:
        seed_response = client.post('/api/analyse',
            headers={'Authorization': f'Bearer {token}'},
            data=json.dumps({'mode': 'daily', 'text': 'seed text', 'reference_date': reference_date}),
            content_type='application/json'
        )
        assert seed_response.status_code == 200

    final_response = client.post('/api/analyse',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({'mode': 'daily', 'text': 'current text', 'reference_date': '2026-05-13'}),
        content_type='application/json'
    )

    assert final_response.status_code == 200
    data = json.loads(final_response.data)
    assert set(data.keys()) == {'ai_response', 'tags', 'daily_people_names', 'daily_places'}

    recent_context = mock_service.analyse_daily_entry.call_args.kwargs['recent_context']
    assert recent_context is not None
    assert recent_context.count('Repeated metadata header') == 1
    assert 'Distinct metadata header' in recent_context

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


def test_upload_daily_attachment_is_serialised_on_entry_detail(client):
    token = get_auth_token(client)

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
    assert attachment['url'].startswith('http://localhost/media/')

    detail_response = client.get(
        f'/api/daily/{entry_id}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert detail_response.status_code == 200
    detail_data = json.loads(detail_response.data)
    assert len(detail_data['attachments']) == 1
    assert detail_data['attachments'][0]['original_filename'] == 'notes.pdf'


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

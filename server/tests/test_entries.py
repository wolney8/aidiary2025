# server/tests/test_entries.py
# Entries CRUD tests
import pytest
import json
from app import create_app
import tempfile
import os
from unittest.mock import patch, MagicMock
from routes.analyse import ANALYSE_TEXT_MAX_LENGTH
from services.openai_svc import AnalysisRateLimitError

@pytest.fixture
def client():
    """Create test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
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
                entry_number INTEGER,
                title TEXT,
                user_message TEXT,
                ai_response TEXT,
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


@pytest.fixture
def client_schema_without_mood_columns():
    """Create test client where diary tables start without mood/ai_style columns."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
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


@pytest.fixture
def client_schema_without_analysis_columns():
    """Create test client where analysis result columns are missing initially."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
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

def test_create_daily_entry(client):
    """Test creating a daily entry."""
    token = get_auth_token(client)
    
    response = client.post('/api/daily',
        headers={'Authorization': f'Bearer {token}'},
        data=json.dumps({
            'entry_date': '2024-01-15',
            'user_message': 'Today was a good day'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'id' in data
    assert data['entry_number'] == 1

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

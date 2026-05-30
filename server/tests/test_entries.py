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
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
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
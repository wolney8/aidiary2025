# server/tests/test_entries.py
# Entries CRUD tests
import pytest
import json
from app import create_app
import tempfile
import os
from unittest.mock import patch, MagicMock

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
                user_message TEXT,
                ai_response TEXT,
                daily_people_names TEXT,
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
        'people_names': 'John,Sarah'
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

def test_unauthorised_access(client):
    """Test accessing protected endpoint without token."""
    response = client.get('/api/daily')
    assert response.status_code == 401
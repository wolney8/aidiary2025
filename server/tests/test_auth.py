# server/tests/test_auth.py
# Authentication tests
import pytest
import json
from app import create_app
import tempfile
import os

@pytest.fixture
def client():
    """Create test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'
    
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        # Create tables in test database
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
        conn.commit()
        conn.close()
        
        yield client
    
    os.close(db_fd)
    os.unlink(db_path)

def test_register_success(client):
    """Test successful user registration."""
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert 'token' in data
    assert data['user']['username'] == 'testuser'

def test_register_missing_credentials(client):
    """Test registration with missing credentials."""
    response = client.post('/api/register',
        data=json.dumps({'username': 'testuser'}),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data

def test_register_rejects_short_password(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'short'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Password must be between 8 and 12 characters'

def test_register_rejects_password_that_is_only_numbers(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': '12345678'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Password cannot be only numbers'

def test_register_rejects_password_without_number(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'abcdefgh'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Password must include at least one number'

def test_register_rejects_password_over_max_length(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'abc1234567890'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Password must be between 8 and 12 characters'

def test_register_trims_username(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': '  spaceduser  ',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['user']['username'] == 'spaceduser'

def test_register_rejects_invalid_username_characters(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'bad user!',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Username may only contain letters, numbers, dots, underscores, and hyphens'

def test_register_rejects_overlong_names(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'testpass123',
            'first_name': 'A' * 13
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'First and last name must be 12 characters or fewer'

def test_register_rejects_invalid_name_characters(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'testpass1',
            'first_name': '<script>'
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'First name contains unsupported characters'

def test_register_rejects_duplicate_username(client):
    first_response = client.post('/api/register',
        data=json.dumps({
            'username': 'repeatuser',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )
    assert first_response.status_code == 201

    second_response = client.post('/api/register',
        data=json.dumps({
            'username': 'repeatuser',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )

    assert second_response.status_code == 409
    data = json.loads(second_response.data)
    assert data['error'] == 'Username already exists'

def test_login_success(client):
    """Test successful login."""
    # First register a user
    client.post('/api/register',
        data=json.dumps({
            'username': 'testuser',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )
    
    # Then try to login
    response = client.post('/api/login',
        data=json.dumps({
            'username': 'testuser',
            'password': 'testpass123'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'token' in data
    assert 'user' in data

def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post('/api/login',
        data=json.dumps({
            'username': 'nonexistent',
            'password': 'wrongpass'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'error' in data

def test_login_migrates_legacy_plaintext_password_to_bcrypt(client):
    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    conn.execute("""
        INSERT INTO users (id, username, password, first_name, last_name)
        VALUES (?, ?, ?, ?, ?)
    """, (99, 'legacyuser', 'legacy-pass-123', 'Legacy', 'User'))
    conn.commit()
    conn.close()

    response = client.post('/api/login',
        data=json.dumps({
            'username': 'legacyuser',
            'password': 'legacy-pass-123'
        }),
        content_type='application/json'
    )

    assert response.status_code == 200

    conn = sqlite3.connect(os.environ['DB_PATH'])
    updated_password = conn.execute(
        'SELECT password FROM users WHERE id = ?',
        (99,)
    ).fetchone()[0]
    conn.close()

    assert updated_password.startswith('$2b$')

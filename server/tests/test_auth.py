# server/tests/test_auth.py
# Authentication tests
import pytest
import json
from app import create_app
import tempfile
import os
from flask import Flask
from routes import auth


class _FakeAuthAdapter:
    def table_columns(self, _conn, table_name):
        assert table_name == 'users'
        return {'profile_picture_storage_key', 'writing_reminder_time'}


def test_production_startup_requires_explicit_jwt_secret(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('JWT_SECRET', raising=False)

    with pytest.raises(RuntimeError, match='JWT_SECRET must be configured'):
        create_app()


def test_auth_helpers_support_postgres_placeholders_and_optional_selects():
    app = Flask(__name__)
    app.config['DATABASE_PROVIDER'] = 'postgres'
    app.config['DATABASE_ADAPTER'] = _FakeAuthAdapter()

    with app.app_context():
        optional_selects = auth._optional_user_selects(object())
        insert_sql = auth._sql(
            auth.append_returning_id(
                '''
                INSERT INTO users (username, password, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ''',
                auth._database_provider(),
            )
        )
        login_sql = auth._sql(
            f'''SELECT id, username, password, first_name, {optional_selects}
                FROM users WHERE username = ?'''
        )

    assert 'profile_picture_storage_key' in optional_selects
    assert "'19:00' AS writing_reminder_time" not in optional_selects
    assert "'daily,dream' AS writing_reminder_entry_types" in optional_selects
    assert '1 AS chat_enabled' in optional_selects
    assert 'VALUES (%s, %s, %s, %s)' in insert_sql
    assert 'RETURNING id' in insert_sql
    assert 'WHERE username = %s' in login_sql


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
    assert data['error'] == 'Password must be between 8 and 128 characters'

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
            'password': f"a1{'x' * 127}"
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['error'] == 'Password must be between 8 and 128 characters'


def test_register_accepts_long_passphrase(client):
    response = client.post('/api/register',
        data=json.dumps({
            'username': 'passphrase-user',
            'password': 'correct-horse-battery-staple-2026'
        }),
        content_type='application/json'
    )

    assert response.status_code == 201

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


def test_oauth_providers_report_disabled_when_unconfigured(client, monkeypatch):
    for provider in ("GOOGLE", "MICROSOFT"):
        monkeypatch.delenv(f"OAUTH_{provider}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"OAUTH_{provider}_CLIENT_SECRET", raising=False)
        monkeypatch.delenv(f"OAUTH_{provider}_REDIRECT_URI", raising=False)

    response = client.get("/api/oauth/providers")

    assert response.status_code == 200
    payload = json.loads(response.data)
    providers = {provider["id"]: provider for provider in payload["providers"]}
    assert providers["google"]["label"] == "Google"
    assert providers["google"]["configured"] is False
    assert providers["google"]["enabled"] is False
    assert providers["google"]["status"] == "not_configured"
    assert providers["microsoft"]["configured"] is False
    assert providers["microsoft"]["enabled"] is False


def test_oauth_providers_enable_configured_provider_without_exposing_secret(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.delenv("OAUTH_MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("OAUTH_MICROSOFT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OAUTH_MICROSOFT_REDIRECT_URI", raising=False)

    response = client.get("/api/oauth/providers")

    assert response.status_code == 200
    payload = json.loads(response.data)
    providers = {provider["id"]: provider for provider in payload["providers"]}
    assert providers["google"]["configured"] is True
    assert providers["google"]["enabled"] is True
    assert providers["google"]["status"] == "enabled"
    assert providers["google"]["start_url"] == "/api/oauth/google/start"
    assert "google-secret" not in response.get_data(as_text=True)
    assert providers["microsoft"]["configured"] is False


def test_oauth_start_redirects_to_provider_with_signed_state(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")

    response = client.get("/api/oauth/google/start?returnUrl=/entries")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=google-client" in location
    assert "scope=openid+email+profile" in location
    assert "state=" in location


class _OAuthResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_oauth_callback_creates_user_identity_and_redirects_to_frontend(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:4200")
    with client.application.app_context():
        state = auth._sign_oauth_state({
            "provider": "google",
            "return_url": "/dashboard",
            "nonce": "test",
        })

    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *_args, **_kwargs: _OAuthResponse({"access_token": "provider-token"}),
    )
    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda *_args, **_kwargs: _OAuthResponse({
            "sub": "google-user-123",
            "email": "OAuthUser@example.com",
            "email_verified": True,
            "name": "OAuth User",
            "given_name": "OAuth",
            "family_name": "User",
            "picture": "https://example.test/avatar.jpg",
        }),
    )

    response = client.get(f"/api/oauth/google/callback?code=abc&state={state}")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("http://localhost:4200/oauth/callback#")
    assert "token=" in response.headers["Location"]
    assert "returnUrl=%2Fdashboard" in response.headers["Location"]
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        identity = conn.execute(
            "SELECT provider, provider_subject, email, email_verified FROM auth_identities"
        ).fetchone()
        user = conn.execute("SELECT username, first_name, last_name FROM users").fetchone()
    assert identity == ("google", "google-user-123", "oauthuser@example.com", 1)
    assert user == ("oauthuser", "OAuth", "User")


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


def test_login_rejects_unusable_password_hash_without_crashing(client):
    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    conn.execute("""
        INSERT INTO users (id, username, password, first_name, last_name)
        VALUES (?, ?, ?, ?, ?)
    """, (100, 'provideruser', '$2b$not-a-valid-hash', 'Provider', 'User'))
    conn.commit()
    conn.close()

    response = client.post('/api/login',
        data=json.dumps({
            'username': 'provideruser',
            'password': 'anything123'
        }),
        content_type='application/json'
    )

    assert response.status_code == 401

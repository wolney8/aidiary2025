# server/tests/test_auth.py
# Authentication tests
import pytest
import json
import base64
from app import create_app
import tempfile
import os
import shutil
from urllib.parse import parse_qs, urlparse
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
    assert '1 AS password_auth_enabled' in optional_selects
    assert '1 AS onboarding_completed' in optional_selects
    assert 'VALUES (%s, %s, %s, %s)' in insert_sql
    assert 'RETURNING id' in insert_sql
    assert 'WHERE username = %s' in login_sql


@pytest.fixture
def client():
    """Create test client with temporary database."""
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    os.environ['DB_PATH'] = db_path
    os.environ['JWT_SECRET'] = 'test-secret'
    os.environ['MEDIA_ROOT'] = media_root
    os.environ['AUTH_LOGIN_RATE_LIMIT'] = '1000 per minute'
    os.environ['AUTH_REGISTER_RATE_LIMIT'] = '1000 per minute'
    os.environ['AUTH_OAUTH_START_RATE_LIMIT'] = '1000 per minute'
    os.environ['AUTH_OAUTH_CALLBACK_RATE_LIMIT'] = '1000 per minute'
    
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
                email TEXT,
                email_verified INTEGER DEFAULT 0,
                first_name TEXT,
                last_name TEXT,
                age INTEGER,
                sex TEXT,
                goals TEXT,
                dailydiary_api_key TEXT,
                dreamdiary_api_key TEXT,
                chatgpt_daily_diary_coachname TEXT,
                chatgpt_dream_diary_coachname TEXT,
                display_name TEXT,
                gender TEXT,
                profile_picture_storage_key TEXT,
                writing_reminders_enabled INTEGER DEFAULT 0,
                writing_reminder_days TEXT,
                writing_reminder_time TEXT DEFAULT '19:00',
                writing_reminder_silence_days INTEGER DEFAULT 3,
                writing_reminder_entry_types TEXT DEFAULT 'daily,dream',
                writing_rhythm_progress_enabled INTEGER DEFAULT 0,
                writing_rhythm_weekly_goal INTEGER DEFAULT 4,
                chat_enabled INTEGER DEFAULT 1,
                password_auth_enabled INTEGER DEFAULT 1,
                onboarding_completed INTEGER DEFAULT 1
            )
        ''')
        conn.commit()
        conn.close()
        
        yield client
    
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(media_root, ignore_errors=True)

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
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        event = conn.execute(
            """
            SELECT event_type, outcome, user_id
            FROM security_audit_events
            WHERE event_type = 'register_success'
            """
        ).fetchone()
    assert event == ("register_success", "success", 1)


def test_register_with_email_creates_verification_token(client, monkeypatch):
    sent_messages = []

    def fake_send(**kwargs):
        sent_messages.append(kwargs)

    monkeypatch.setattr(auth, "send_transactional_email", fake_send)

    response = client.post('/api/register',
        data=json.dumps({
            'username': 'emailuser',
            'password': 'testpass123',
            'email': 'EmailUser@example.com',
        }),
        content_type='application/json'
    )

    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['user']['email'] == 'emailuser@example.com'
    assert data['user']['email_verified'] is False
    assert sent_messages
    assert 'verify-email?token=' in sent_messages[0]['text_body']
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        token_row = conn.execute(
            """
            SELECT purpose, consumed_at
            FROM account_security_tokens
            WHERE user_id = 1
            """
        ).fetchone()
    assert token_row == ("email_verification", None)


def test_register_can_require_email_when_public_flag_enabled(client, monkeypatch):
    monkeypatch.setenv("OPENMYND_REQUIRE_REGISTRATION_EMAIL", "true")

    response = client.post('/api/register',
        data=json.dumps({
            'username': 'needs-email',
            'password': 'testpass123',
        }),
        content_type='application/json'
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == "A valid email address is required"

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


def test_oauth_provider_discovery_ignores_placeholder_credentials(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.setenv("OAUTH_MICROSOFT_CLIENT_ID", "your-microsoft-application-client-id")
    monkeypatch.setenv("OAUTH_MICROSOFT_CLIENT_SECRET", "your-microsoft-client-secret-value")
    monkeypatch.setenv("OAUTH_MICROSOFT_REDIRECT_URI", "http://localhost:5001/api/oauth/microsoft/callback")

    response = client.get("/api/oauth/providers")

    assert response.status_code == 200
    payload = json.loads(response.data)
    providers = {provider["id"]: provider for provider in payload["providers"]}
    assert providers["google"]["enabled"] is True
    assert providers["microsoft"]["configured"] is False
    assert providers["microsoft"]["enabled"] is False


def test_oauth_start_redirects_to_provider_with_signed_state(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.delenv("OAUTH_GOOGLE_EXTENDED_PROFILE", raising=False)

    response = client.get("/api/oauth/google/start?returnUrl=/entries")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=google-client" in location
    assert "scope=openid+email+profile" in location
    assert "include_granted_scopes=true" in location
    assert "prompt=" not in location
    assert "state=" in location


def test_oauth_start_rate_limit_is_enforced(client, monkeypatch):
    monkeypatch.setenv("AUTH_OAUTH_START_RATE_LIMIT", "1 per minute")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")

    first = client.get("/api/oauth/google/start")
    second = client.get("/api/oauth/google/start")

    assert first.status_code == 302
    assert second.status_code == 429
    assert json.loads(second.data)["error"] == "Too many attempts. Try again shortly."


def test_oauth_start_keeps_google_login_scopes_minimal_even_when_extended_profile_enabled(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.setenv("OAUTH_GOOGLE_EXTENDED_PROFILE", "true")

    response = client.get("/api/oauth/google/start")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert "scope=openid+email+profile" in location
    assert "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuser.birthday.read" not in location
    assert "https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuser.gender.read" not in location
    assert "prompt=" not in location


class _OAuthResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _OAuthBinaryResponse:
    def __init__(self, content: bytes, content_type: str):
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        return None


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
    assert response.headers["Location"].startswith("http://localhost:4200/onboarding#")
    assert "token=" in response.headers["Location"]
    assert "returnUrl=%2Fdashboard" in response.headers["Location"]
    fragment = parse_qs(urlparse(response.headers["Location"]).fragment)
    assert fragment["onboardingRequired"] == ["true"]
    encoded_user = fragment["user"][0]
    padded_user = encoded_user + "=" * (-len(encoded_user) % 4)
    auth_user = json.loads(base64.urlsafe_b64decode(padded_user.encode()).decode())
    assert auth_user["onboarding_completed"] is False
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        identity = conn.execute(
            "SELECT provider, provider_subject, email, email_verified FROM auth_identities"
        ).fetchone()
        user = conn.execute(
            """
            SELECT username, first_name, last_name, display_name,
                   password_auth_enabled, onboarding_completed
            FROM users
            """
        ).fetchone()
    assert identity == ("google", "google-user-123", "oauthuser@example.com", 1)
    assert user == ("oauthuser", "OAuth", "User", "OAuth", 0, 0)


def test_oauth_callback_existing_completed_user_does_not_require_onboarding(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:4200")
    with client.application.app_context():
        state = auth._sign_oauth_state({
            "provider": "google",
            "return_url": "/account",
            "nonce": "test",
        })

    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute(
            """
            INSERT INTO users (
                id, username, password, first_name, last_name,
                password_auth_enabled, onboarding_completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (42, "existing-google", "unused", "Existing", "User", 0, 1),
        )
        conn.execute(
            """
            INSERT INTO auth_identities (
                user_id, provider, provider_subject, email, email_verified
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (42, "google", "google-existing-123", "existing@example.com", 1),
        )

    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *_args, **_kwargs: _OAuthResponse({"access_token": "provider-token"}),
    )
    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda *_args, **_kwargs: _OAuthResponse({
            "sub": "google-existing-123",
            "email": "Existing@example.com",
            "email_verified": True,
            "name": "Existing User",
            "given_name": "Existing",
            "family_name": "User",
        }),
    )

    response = client.get(f"/api/oauth/google/callback?code=abc&state={state}")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("http://localhost:4200/oauth/callback#")
    fragment = parse_qs(urlparse(response.headers["Location"]).fragment)
    assert fragment["onboardingRequired"] == ["false"]
    assert fragment["returnUrl"] == ["/account"]


def test_oauth_callback_existing_incomplete_user_requires_onboarding(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.setenv("FRONTEND_BASE_URL", "http://localhost:4200")
    with client.application.app_context():
        state = auth._sign_oauth_state({
            "provider": "google",
            "return_url": "/account",
            "nonce": "test",
        })

    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute(
            """
            INSERT INTO users (
                id, username, password, first_name, last_name,
                password_auth_enabled, onboarding_completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (43, "incomplete-google", "unused", "Incomplete", "User", 0, 0),
        )
        conn.execute(
            """
            INSERT INTO auth_identities (
                user_id, provider, provider_subject, email, email_verified
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (43, "google", "google-incomplete-123", "incomplete@example.com", 1),
        )

    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *_args, **_kwargs: _OAuthResponse({"access_token": "provider-token"}),
    )
    monkeypatch.setattr(
        auth.httpx,
        "get",
        lambda *_args, **_kwargs: _OAuthResponse({
            "sub": "google-incomplete-123",
            "email": "Incomplete@example.com",
            "email_verified": True,
            "name": "Incomplete User",
            "given_name": "Incomplete",
            "family_name": "User",
        }),
    )

    response = client.get(f"/api/oauth/google/callback?code=abc&state={state}")

    assert response.status_code == 302
    assert response.headers["Location"].startswith("http://localhost:4200/onboarding#")
    fragment = parse_qs(urlparse(response.headers["Location"]).fragment)
    assert fragment["onboardingRequired"] == ["true"]
    assert fragment["returnUrl"] == ["/dashboard"]


def test_google_oauth_imports_profile_picture_and_extended_profile(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_ID", "google-client")
    monkeypatch.setenv("OAUTH_GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("OAUTH_GOOGLE_REDIRECT_URI", "http://localhost:5001/api/oauth/google/callback")
    monkeypatch.setenv("OAUTH_GOOGLE_EXTENDED_PROFILE", "true")
    with client.application.app_context():
        state = auth._sign_oauth_state({
            "provider": "google",
            "return_url": "/dashboard",
            "nonce": "test",
            "extended_profile": True,
        })

    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *_args, **_kwargs: _OAuthResponse({"access_token": "provider-token"}),
    )

    from io import BytesIO
    from PIL import Image

    image = BytesIO()
    Image.new("RGB", (80, 80), (66, 133, 244)).save(image, format="PNG")

    def fake_get(url, *_args, **_kwargs):
        url_text = str(url)
        if "people.googleapis.com" in url_text:
            return _OAuthResponse({
                "birthdays": [{"date": {"year": 1990, "month": 2, "day": 3}}],
                "genders": [{"value": "male"}],
                "locales": [{"value": "en-GB"}],
            })
        if "openidconnect.googleapis.com" in url_text:
            return _OAuthResponse({
                "sub": "google-user-with-photo",
                "email": "photo@example.com",
                "email_verified": True,
                "name": "Photo User",
                "given_name": "Photo",
                "family_name": "User",
                "picture": "https://lh3.googleusercontent.com/a/photo",
            })
        return _OAuthBinaryResponse(image.getvalue(), "image/png")

    monkeypatch.setattr(auth.httpx, "get", fake_get)

    response = client.get(f"/api/oauth/google/callback?code=abc&state={state}")

    assert response.status_code == 302
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        user = conn.execute(
            """
            SELECT profile_picture_storage_key, age, gender
            FROM users
            """
        ).fetchone()
    assert user[0].startswith("profiles/1/")
    assert user[1] >= 35
    assert user[2] == "man"
    assert os.path.exists(os.path.join(os.environ["MEDIA_ROOT"], user[0]))


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
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        events = conn.execute(
            """
            SELECT event_type, outcome, user_id
            FROM security_audit_events
            WHERE event_type IN ('register_success', 'login_success')
            ORDER BY id
            """
        ).fetchall()
    assert events == [
        ("register_success", "success", 1),
        ("login_success", "success", 1),
    ]


def test_cookie_auth_mode_sets_and_clears_access_cookie(client):
    """Cookie mode is additive while bearer-token compatibility remains active."""
    client.application.config['OPENMYND_AUTH_COOKIE_MODE'] = True
    client.application.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
    client.application.config['JWT_COOKIE_CSRF_PROTECT'] = False

    client.post('/api/register',
        data=json.dumps({
            'username': 'cookieuser',
            'password': 'password123',
            'first_name': 'Cookie',
            'last_name': 'User',
        }),
        content_type='application/json'
    )

    response = client.post('/api/login',
        data=json.dumps({
            'username': 'cookieuser',
            'password': 'password123',
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    assert 'token' in json.loads(response.data)
    set_cookie_headers = response.headers.getlist('Set-Cookie')
    assert any('access_token_cookie=' in header for header in set_cookie_headers)
    assert any('HttpOnly' in header for header in set_cookie_headers)

    logout_response = client.post('/api/logout')
    logout_cookie_headers = logout_response.headers.getlist('Set-Cookie')
    assert logout_response.status_code == 200
    assert any(
        'access_token_cookie=' in header
        and 'Expires=Thu, 01 Jan 1970 00:00:00 GMT' in header
        for header in logout_cookie_headers
    )


def test_cookie_auth_mode_with_csrf_sets_csrf_cookie(client):
    client.application.config['OPENMYND_AUTH_COOKIE_MODE'] = True
    client.application.config['JWT_TOKEN_LOCATION'] = ['headers', 'cookies']
    client.application.config['JWT_COOKIE_CSRF_PROTECT'] = True

    client.post('/api/register',
        data=json.dumps({
            'username': 'csrfcookieuser',
            'password': 'password123',
            'first_name': 'Cookie',
            'last_name': 'Csrf',
        }),
        content_type='application/json'
    )

    response = client.post('/api/login',
        data=json.dumps({
            'username': 'csrfcookieuser',
            'password': 'password123',
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    set_cookie_headers = response.headers.getlist('Set-Cookie')
    assert any('access_token_cookie=' in header for header in set_cookie_headers)
    assert any('csrf_access_token=' in header for header in set_cookie_headers)


def test_login_records_auth_session(client):
    client.post('/api/register',
        data=json.dumps({
            'username': 'sessionuser',
            'password': 'password123',
            'first_name': 'Session',
            'last_name': 'User',
        }),
        content_type='application/json'
    )

    response = client.post('/api/login',
        data=json.dumps({
            'username': 'sessionuser',
            'password': 'password123',
        }),
        content_type='application/json'
    )

    assert response.status_code == 200
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT user_id, jwt_jti, expires_at, revoked_at
            FROM auth_sessions
            ORDER BY id
            """
        ).fetchall()
    assert len(rows) >= 2
    latest = rows[-1]
    assert latest["user_id"] == 1
    assert latest["jwt_jti"]
    assert latest["expires_at"]
    assert latest["revoked_at"] is None


def test_logout_revokes_current_auth_session(client):
    client.post('/api/register',
        data=json.dumps({
            'username': 'logoutsession',
            'password': 'password123',
            'first_name': 'Logout',
            'last_name': 'Session',
        }),
        content_type='application/json'
    )
    login_response = client.post('/api/login',
        data=json.dumps({
            'username': 'logoutsession',
            'password': 'password123',
        }),
        content_type='application/json'
    )
    token = json.loads(login_response.data)['token']

    logout_response = client.post(
        '/api/logout',
        headers={'Authorization': f'Bearer {token}'},
    )
    protected_response = client.post(
        '/api/auth/email/verification/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert logout_response.status_code == 200
    assert protected_response.status_code == 401
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT revoked_at, revoked_reason
            FROM auth_sessions
            WHERE revoked_reason = 'logout'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert row is not None
    assert row["revoked_at"]
    assert row["revoked_reason"] == "logout"


def test_account_delete_revokes_user_sessions_before_deleting_account(client):
    client.post('/api/register',
        data=json.dumps({
            'username': 'deletesession',
            'password': 'password123',
            'first_name': 'Delete',
            'last_name': 'Session',
        }),
        content_type='application/json'
    )
    login_response = client.post('/api/login',
        data=json.dumps({
            'username': 'deletesession',
            'password': 'password123',
        }),
        content_type='application/json'
    )
    token = json.loads(login_response.data)['token']

    delete_response = client.delete(
        '/api/profile/account',
        data=json.dumps({
            'password': 'password123',
            'confirmation': 'DELETE MY ACCOUNT',
        }),
        content_type='application/json',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert delete_response.status_code == 200
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        user = conn.execute(
            "SELECT id FROM users WHERE username = 'deletesession'"
        ).fetchone()
        revoked = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM auth_sessions
            WHERE user_id = 1
              AND revoked_reason = 'account_deleted'
              AND revoked_at IS NOT NULL
            """
        ).fetchone()
    assert user is None
    assert revoked["total"] >= 1


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
    import sqlite3
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        event = conn.execute(
            """
            SELECT event_type, outcome, user_id, metadata_json
            FROM security_audit_events
            WHERE event_type = 'login_failed'
            """
        ).fetchone()
    assert event[0:3] == ("login_failed", "rejected", None)
    assert json.loads(event[3]) == {"reason": "unknown_user"}


def test_login_rate_limit_is_enforced(client, monkeypatch):
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT", "2 per minute")

    first = client.post('/api/login',
        data=json.dumps({
            'username': 'nonexistent',
            'password': 'wrongpass'
        }),
        content_type='application/json'
    )
    second = client.post('/api/login',
        data=json.dumps({
            'username': 'nonexistent',
            'password': 'wrongpass'
        }),
        content_type='application/json'
    )
    third = client.post('/api/login',
        data=json.dumps({
            'username': 'nonexistent',
            'password': 'wrongpass'
        }),
        content_type='application/json'
    )

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert json.loads(third.data)["error"] == "Too many attempts. Try again shortly."

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


def test_login_blocks_legacy_plaintext_password_when_fallback_disabled(client, monkeypatch):
    monkeypatch.setenv('OPENMYND_DISABLE_LEGACY_PASSWORD_FALLBACK', 'true')
    import sqlite3
    conn = sqlite3.connect(os.environ['DB_PATH'])
    conn.execute("""
        INSERT INTO users (id, username, password, first_name, last_name)
        VALUES (?, ?, ?, ?, ?)
    """, (101, 'blockedlegacy', 'legacy-pass-123', 'Legacy', 'Blocked'))
    conn.commit()
    conn.close()

    response = client.post('/api/login',
        data=json.dumps({
            'username': 'blockedlegacy',
            'password': 'legacy-pass-123'
        }),
        content_type='application/json'
    )

    assert response.status_code == 401

    conn = sqlite3.connect(os.environ['DB_PATH'])
    stored_password = conn.execute(
        'SELECT password FROM users WHERE id = ?',
        (101,)
    ).fetchone()[0]
    conn.close()

    assert stored_password == 'legacy-pass-123'


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


def test_email_verification_confirm_marks_user_verified(client, monkeypatch):
    sent_messages = []

    def fake_send(**kwargs):
        sent_messages.append(kwargs)

    monkeypatch.setattr(auth, "send_transactional_email", fake_send)
    register_response = client.post('/api/register',
        data=json.dumps({
            'username': 'verifyuser',
            'password': 'testpass123',
            'email': 'verify@example.com',
        }),
        content_type='application/json'
    )
    token = sent_messages[0]['text_body'].split('token=', maxsplit=1)[1].split()[0]

    response = client.post('/api/auth/email/verification/confirm',
        data=json.dumps({'token': token}),
        content_type='application/json'
    )

    assert register_response.status_code == 201
    assert response.status_code == 200
    import sqlite3
    with sqlite3.connect(os.environ['DB_PATH']) as conn:
        verified = conn.execute(
            'SELECT email_verified FROM users WHERE username = ?',
            ('verifyuser',),
        ).fetchone()[0]
        consumed_at = conn.execute(
            'SELECT consumed_at FROM account_security_tokens'
        ).fetchone()[0]
    assert verified == 1
    assert consumed_at


def test_password_reset_request_and_confirm_changes_password(client, monkeypatch):
    sent_messages = []

    def fake_send(**kwargs):
        sent_messages.append(kwargs)

    monkeypatch.setattr(auth, "send_transactional_email", fake_send)
    client.post('/api/register',
        data=json.dumps({
            'username': 'resetuser',
            'password': 'oldpass123',
            'email': 'reset@example.com',
        }),
        content_type='application/json'
    )
    sent_messages.clear()

    request_response = client.post('/api/auth/password-reset/request',
        data=json.dumps({'email': 'reset@example.com'}),
        content_type='application/json'
    )
    token = sent_messages[0]['text_body'].split('token=', maxsplit=1)[1].split()[0]
    confirm_response = client.post('/api/auth/password-reset/confirm',
        data=json.dumps({'token': token, 'password': 'newpass123'}),
        content_type='application/json'
    )
    login_response = client.post('/api/login',
        data=json.dumps({'username': 'resetuser', 'password': 'newpass123'}),
        content_type='application/json'
    )

    assert request_response.status_code == 202
    assert confirm_response.status_code == 200
    assert login_response.status_code == 200


def test_password_reset_request_does_not_reveal_unknown_email(client):
    response = client.post('/api/auth/password-reset/request',
        data=json.dumps({'email': 'unknown@example.com'}),
        content_type='application/json'
    )

    assert response.status_code == 202
    assert json.loads(response.data) == {
        'message': 'If an account exists for that email, a reset link has been sent.'
    }

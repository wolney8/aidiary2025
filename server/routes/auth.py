# Authentication routes with JWT
from flask import Blueprint, request, jsonify, current_app, redirect
from flask_jwt_extended import create_access_token
import bcrypt
import base64
import sqlite3
import re
import os
import secrets
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.media_storage import resolve_image_url
from services.sql_compat import adapt_placeholders, append_returning_id, inserted_id

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_USERNAME_LENGTH = 32
MAX_NAME_LENGTH = 12
USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
NAME_PATTERN = re.compile(r"^[A-Za-z]+(?:[ '-][A-Za-z]+)*$")
OAUTH_PROVIDERS = {
    'google': {
        'label': 'Google',
        'env_prefix': 'GOOGLE',
        'authorization_endpoint': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_endpoint': 'https://oauth2.googleapis.com/token',
        'userinfo_endpoint': 'https://openidconnect.googleapis.com/v1/userinfo',
    },
    'microsoft': {
        'label': 'Microsoft',
        'env_prefix': 'MICROSOFT',
        'authorization_endpoint': 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize',
        'token_endpoint': 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token',
        'userinfo_endpoint': 'https://graph.microsoft.com/oidc/userinfo',
    },
}
OAUTH_STATE_MAX_AGE_SECONDS = 600


def _normalise_username(raw: object) -> str:
    return str(raw or '').strip()


def _normalise_optional_name(raw: object) -> str:
    return str(raw or '').strip()


def _validate_registration_payload(
    username: str,
    password: str,
    first_name: str,
    last_name: str,
) -> str | None:
    if not username or not password:
        return 'Username and password required'
    if len(username) < 3:
        return 'Username must be at least 3 characters'
    if len(username) > MAX_USERNAME_LENGTH:
        return 'Username must be 32 characters or fewer'
    if not USERNAME_PATTERN.fullmatch(username):
        return 'Username may only contain letters, numbers, dots, underscores, and hyphens'
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        return 'Password must be between 8 and 128 characters'
    if password.isdigit():
        return 'Password cannot be only numbers'
    if not any(char.isalpha() for char in password):
        return 'Password must include at least one letter'
    if not any(char.isdigit() for char in password):
        return 'Password must include at least one number'
    if len(first_name) > MAX_NAME_LENGTH or len(last_name) > MAX_NAME_LENGTH:
        return 'First and last name must be 12 characters or fewer'
    if first_name and not NAME_PATTERN.fullmatch(first_name):
        return 'First name contains unsupported characters'
    if last_name and not NAME_PATTERN.fullmatch(last_name):
        return 'Last name contains unsupported characters'
    return None

def get_db():
    """Get database connection."""
    return _database_adapter().connect(timeout=10)


def _database_adapter() -> DatabaseAdapter:
    return current_app.config['DATABASE_ADAPTER']


def _database_provider() -> str:
    return current_app.config.get('DATABASE_PROVIDER', SQLITE_PROVIDER)


def _sql(statement: str) -> str:
    return adapt_placeholders(statement, _database_provider())


def _optional_user_selects(conn) -> str:
    columns = _database_adapter().table_columns(conn, 'users')
    optional_columns = {
        'profile_picture_storage_key': 'NULL',
        'writing_reminders_enabled': '0',
        'writing_reminder_days': "''",
        'writing_reminder_time': "'19:00'",
        'writing_reminder_silence_days': '3',
        'writing_reminder_entry_types': "'daily,dream'",
        'writing_rhythm_progress_enabled': '0',
        'writing_rhythm_weekly_goal': '4',
        'chat_enabled': '1',
    }
    selects = []
    for column_name, fallback in optional_columns.items():
        if column_name in columns:
            selects.append(column_name)
        else:
            selects.append(f'{fallback} AS {column_name}')
    return ', '.join(selects)


def _is_duplicate_username_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return isinstance(exc, sqlite3.IntegrityError) or (
        'users' in message
        and 'username' in message
        and ('unique' in message or 'duplicate' in message)
    )


def _oauth_provider_payload(provider_id: str, config: dict[str, str]) -> dict[str, object]:
    configured = _oauth_provider_is_configured(config)
    return {
        'id': provider_id,
        'label': config['label'],
        'enabled': configured,
        'configured': configured,
        'status': 'enabled' if configured else 'not_configured',
        'start_url': f'/api/oauth/{provider_id}/start' if configured else None,
    }


@auth_bp.route('/oauth/providers', methods=['GET'])
def oauth_providers():
    """Report OAuth/OIDC provider readiness without exposing secrets."""
    return jsonify({
        'providers': [
            _oauth_provider_payload(provider_id, config)
            for provider_id, config in OAUTH_PROVIDERS.items()
        ],
    }), 200


@auth_bp.route('/oauth/<provider_id>/start', methods=['GET'])
def oauth_start(provider_id: str):
    config = _oauth_config(provider_id)
    if not config:
        return jsonify({'error': 'Unsupported OAuth provider'}), 404
    if not _oauth_provider_is_configured(config):
        return jsonify({'error': 'OAuth provider is not configured'}), 503

    return_url = _safe_return_url(request.args.get('returnUrl'))
    state = _sign_oauth_state({
        'provider': provider_id,
        'return_url': return_url,
        'nonce': secrets.token_urlsafe(16),
    })
    auth_params = {
        'client_id': _oauth_env(config, 'CLIENT_ID'),
        'redirect_uri': _oauth_env(config, 'REDIRECT_URI'),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
    }
    return redirect(f"{_oauth_endpoint(config, 'authorization_endpoint')}?{urlencode(auth_params)}")


@auth_bp.route('/oauth/<provider_id>/callback', methods=['GET'])
def oauth_callback(provider_id: str):
    config = _oauth_config(provider_id)
    if not config:
        return _redirect_oauth_error('Unsupported OAuth provider')
    if request.args.get('error'):
        return _redirect_oauth_error(str(request.args.get('error_description') or request.args.get('error')))

    code = str(request.args.get('code') or '').strip()
    state_token = str(request.args.get('state') or '').strip()
    if not code or not state_token:
        return _redirect_oauth_error('OAuth response was missing required values')

    try:
        state = _load_oauth_state(state_token)
    except SignatureExpired:
        return _redirect_oauth_error('OAuth sign-in expired. Please try again.')
    except BadSignature:
        return _redirect_oauth_error('OAuth sign-in could not be verified.')
    if state.get('provider') != provider_id:
        return _redirect_oauth_error('OAuth provider did not match the sign-in request.')

    try:
        provider_profile = _exchange_oauth_profile(config, code)
        user_id = _get_or_create_oauth_user(provider_id, provider_profile)
    except Exception as exc:
        current_app.logger.warning('OAuth callback failed for %s: %s', provider_id, exc)
        return _redirect_oauth_error('External sign-in failed. Please try again.')

    access_token = create_access_token(identity=str(user_id))
    with get_db() as conn:
        user = _load_user_for_auth(conn, user_id)
    if not user:
        return _redirect_oauth_error('OpenMynd account could not be loaded.')
    return _redirect_oauth_success(access_token, _serialise_auth_user(user), str(state.get('return_url') or '/dashboard'))


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user with bcrypt password hashing."""
    data = request.get_json() or {}
    username = _normalise_username(data.get('username'))
    password = str(data.get('password') or '')
    first_name = _normalise_optional_name(data.get('first_name'))
    last_name = _normalise_optional_name(data.get('last_name'))

    validation_error = _validate_registration_payload(
        username, password, first_name, last_name
    )
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    # Hash password with bcrypt
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        with get_db() as conn:
            existing_user = conn.execute(
                _sql('SELECT id FROM users WHERE username = ?'),
                (username,),
            ).fetchone()
            if existing_user:
                return jsonify({'error': 'Username already exists'}), 409

            cursor = conn.execute(
                _sql(append_returning_id(
                    '''
                    INSERT INTO users (username, password, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                    ''',
                    _database_provider(),
                )),
                (username, password_hash.decode('utf-8'), first_name, last_name),
            )
            user_id = inserted_id(cursor, _database_provider())
        
        # Create JWT token
        access_token = create_access_token(identity=str(user_id))
        
        return jsonify({
            'token': access_token,
            'user': {
                'id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'profile_picture_url': None,
                'writing_reminders_enabled': False,
                'writing_reminder_days': '',
                'writing_reminder_time': '19:00',
                'writing_reminder_silence_days': 3,
                'writing_reminder_entry_types': 'daily,dream',
                'writing_rhythm_progress_enabled': False,
                'writing_rhythm_weekly_goal': 4,
                'chat_enabled': True,
            }
        }), 201
        
    except Exception as exc:
        if _is_duplicate_username_error(exc):
            return jsonify({'error': 'Username already exists'}), 409
        raise

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT token."""
    data = request.get_json() or {}
    username = _normalise_username(data.get('username'))
    password = str(data.get('password') or '')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    with get_db() as conn:
        optional_user_selects = _optional_user_selects(conn)
        user = conn.execute(
            _sql(f'''SELECT id, username, password, first_name, {optional_user_selects}
                FROM users WHERE username = ?'''),
            (username,)
        ).fetchone()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check password (handle both bcrypt and legacy plaintext)
    stored_password = user['password'] or ''
    if stored_password.startswith('$2b$'):  # bcrypt hash
        try:
            password_matches = bcrypt.checkpw(
                password.encode('utf-8'),
                stored_password.encode('utf-8'),
            )
        except ValueError:
            password_matches = False
        if not password_matches:
            return jsonify({'error': 'Invalid credentials'}), 401
    else:  # Legacy plaintext (should be migrated)
        if password != stored_password:
            return jsonify({'error': 'Invalid credentials'}), 401
        # Migrate legacy plaintext password to bcrypt on successful login.
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with get_db() as conn:
            conn.execute(
                _sql('UPDATE users SET password = ? WHERE id = ?'),
                (password_hash.decode('utf-8'), user['id']),
            )
    
    # Create JWT token
    access_token = create_access_token(identity=str(user['id']))
    
    return jsonify({
        'token': access_token,
        'user': _serialise_auth_user(user),
    }), 200


def _oauth_provider_is_configured(config: dict[str, str]) -> bool:
    prefix = config['env_prefix']
    required_env = [
        f'OAUTH_{prefix}_CLIENT_ID',
        f'OAUTH_{prefix}_CLIENT_SECRET',
        f'OAUTH_{prefix}_REDIRECT_URI',
    ]
    return all(os.getenv(name, '').strip() for name in required_env)


def _oauth_config(provider_id: str) -> dict[str, str] | None:
    return OAUTH_PROVIDERS.get(str(provider_id or '').strip().lower())


def _oauth_env(config: dict[str, str], suffix: str) -> str:
    return os.getenv(f"OAUTH_{config['env_prefix']}_{suffix}", '').strip()


def _oauth_endpoint(config: dict[str, str], key: str) -> str:
    endpoint = str(config[key])
    tenant = os.getenv('OAUTH_MICROSOFT_TENANT', 'common').strip() or 'common'
    return endpoint.format(tenant=tenant)


def _state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config['JWT_SECRET_KEY'],
        salt='openmynd-oauth-state-v1',
    )


def _sign_oauth_state(payload: dict[str, object]) -> str:
    return _state_serializer().dumps(payload)


def _load_oauth_state(token: str) -> dict[str, object]:
    value = _state_serializer().loads(token, max_age=OAUTH_STATE_MAX_AGE_SECONDS)
    return value if isinstance(value, dict) else {}


def _safe_return_url(raw: object) -> str:
    value = str(raw or '').strip()
    if not value or not value.startswith('/') or value.startswith('//'):
        return '/dashboard'
    if '://' in value or value in {'/login', '/register', '/oauth/callback'}:
        return '/dashboard'
    return value


def _frontend_base_url() -> str:
    return os.getenv('FRONTEND_BASE_URL', 'http://localhost:4200').strip().rstrip('/')


def _redirect_oauth_error(message: str):
    params = urlencode({'error': message})
    return redirect(f'{_frontend_base_url()}/oauth/callback?{params}')


def _redirect_oauth_success(token: str, user: dict[str, object], return_url: str):
    encoded_user = base64.urlsafe_b64encode(
        jsonify(user).get_data()
    ).decode('ascii').rstrip('=')
    fragment = urlencode({
        'token': token,
        'user': encoded_user,
        'returnUrl': _safe_return_url(return_url),
    })
    return redirect(f'{_frontend_base_url()}/oauth/callback#{fragment}')


def _exchange_oauth_profile(config: dict[str, str], code: str) -> dict[str, object]:
    token_response = httpx.post(
        _oauth_endpoint(config, 'token_endpoint'),
        data={
            'client_id': _oauth_env(config, 'CLIENT_ID'),
            'client_secret': _oauth_env(config, 'CLIENT_SECRET'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': _oauth_env(config, 'REDIRECT_URI'),
        },
        timeout=12,
    )
    token_response.raise_for_status()
    token_payload = token_response.json()
    access_token = str(token_payload.get('access_token') or '').strip()
    if not access_token:
        raise RuntimeError('OAuth provider did not return an access token')

    userinfo_response = httpx.get(
        _oauth_endpoint(config, 'userinfo_endpoint'),
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=12,
    )
    userinfo_response.raise_for_status()
    profile = userinfo_response.json()
    if not str(profile.get('sub') or '').strip():
        raise RuntimeError('OAuth provider did not return a subject')
    return profile


def _get_or_create_oauth_user(provider_id: str, profile: dict[str, object]) -> int:
    provider_subject = str(profile.get('sub') or '').strip()
    email = str(profile.get('email') or profile.get('preferred_username') or '').strip().lower()
    email_verified = bool(profile.get('email_verified'))
    display_name = str(profile.get('name') or '').strip()
    picture_url = str(profile.get('picture') or '').strip()
    first_name = _safe_name_part(profile.get('given_name'))
    last_name = _safe_name_part(profile.get('family_name'))

    with get_db() as conn:
        identity = conn.execute(
            _sql('SELECT user_id FROM auth_identities WHERE provider = ? AND provider_subject = ?'),
            (provider_id, provider_subject),
        ).fetchone()
        if identity:
            user_id = int(identity['user_id'])
            conn.execute(
                _sql(
                    '''
                    UPDATE auth_identities
                    SET email = ?, email_verified = ?, display_name = ?,
                        profile_picture_url = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE provider = ? AND provider_subject = ?
                    '''
                ),
                (
                    email,
                    1 if email_verified else 0,
                    display_name,
                    picture_url,
                    provider_id,
                    provider_subject,
                ),
            )
            return user_id

        username = _unique_oauth_username(conn, provider_id, email, display_name, provider_subject)
        password_hash = bcrypt.hashpw(secrets.token_urlsafe(32).encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor = conn.execute(
            _sql(append_returning_id(
                '''
                INSERT INTO users (username, password, first_name, last_name)
                VALUES (?, ?, ?, ?)
                ''',
                _database_provider(),
            )),
            (username, password_hash, first_name, last_name),
        )
        user_id = inserted_id(cursor, _database_provider())
        conn.execute(
            _sql(
                '''
                INSERT INTO auth_identities (
                    user_id, provider, provider_subject, email, email_verified,
                    display_name, profile_picture_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                '''
            ),
            (
                user_id,
                provider_id,
                provider_subject,
                email,
                1 if email_verified else 0,
                display_name,
                picture_url,
            ),
        )
        return user_id


def _unique_oauth_username(
    conn,
    provider_id: str,
    email: str,
    display_name: str,
    provider_subject: str,
) -> str:
    base_source = email.split('@')[0] if email else display_name or f'{provider_id}-{provider_subject[:8]}'
    base = re.sub(r'[^A-Za-z0-9._-]+', '-', base_source).strip('.-_').lower()
    if len(base) < 3:
        base = f'{provider_id}-user'
    base = base[:MAX_USERNAME_LENGTH].strip('.-_') or f'{provider_id}-user'
    candidate = base
    suffix = 2
    while conn.execute(_sql('SELECT id FROM users WHERE username = ?'), (candidate,)).fetchone():
        suffix_text = f'-{suffix}'
        candidate = f'{base[:MAX_USERNAME_LENGTH - len(suffix_text)]}{suffix_text}'
        suffix += 1
    return candidate


def _safe_name_part(raw: object) -> str:
    value = str(raw or '').strip()
    if len(value) > MAX_NAME_LENGTH:
        value = value[:MAX_NAME_LENGTH].strip()
    return value if value and NAME_PATTERN.fullmatch(value) else ''


def _load_user_for_auth(conn, user_id: int):
    optional_user_selects = _optional_user_selects(conn)
    return conn.execute(
        _sql(f'''SELECT id, username, first_name, {optional_user_selects}
            FROM users WHERE id = ?'''),
        (user_id,),
    ).fetchone()


def _serialise_auth_user(user) -> dict[str, object]:
    return {
        'id': user['id'],
        'username': user['username'],
        'first_name': user['first_name'],
        'profile_picture_url': resolve_image_url(
            user['profile_picture_storage_key']
        ),
        'writing_reminders_enabled': bool(user['writing_reminders_enabled']),
        'writing_reminder_days': user['writing_reminder_days'] or '',
        'writing_reminder_time': user['writing_reminder_time'] or '19:00',
        'writing_reminder_silence_days': user['writing_reminder_silence_days'] or 3,
        'writing_reminder_entry_types': (
            user['writing_reminder_entry_types'] or 'daily,dream'
        ),
        'writing_rhythm_progress_enabled': bool(
            user['writing_rhythm_progress_enabled']
        ),
        'writing_rhythm_weekly_goal': user['writing_rhythm_weekly_goal'] or 4,
        'chat_enabled': bool(user['chat_enabled']),
    }

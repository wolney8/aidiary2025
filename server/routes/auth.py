# Authentication routes with JWT
from flask import Blueprint, request, jsonify, current_app, redirect
from flask_jwt_extended import create_access_token
import bcrypt
import base64
from io import BytesIO
import sqlite3
import re
import os
import secrets
from datetime import date, datetime, timezone
from urllib.parse import urlencode
from urllib.parse import urlparse

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from PIL import Image, ImageOps, UnidentifiedImageError
from extensions import limiter
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.media_storage import resolve_image_url, store_profile_image
from services.sql_compat import adapt_placeholders, append_returning_id, inserted_id

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_USERNAME_LENGTH = 32
MAX_NAME_LENGTH = 12
MAX_OAUTH_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_SIZE = (400, 400)
PROFILE_IMAGE_JPEG_QUALITY = 88
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
OAUTH_PLACEHOLDER_PREFIXES = ('your-', 'replace-', 'example-')
GOOGLE_PEOPLE_PROFILE_SCOPES = (
    'https://www.googleapis.com/auth/user.birthday.read',
    'https://www.googleapis.com/auth/user.gender.read',
    'https://www.googleapis.com/auth/profile.language.read',
)
GOOGLE_SIGN_IN_SCOPES = ('openid', 'email', 'profile')


def _configured_rate_limit(env_name: str, default: str) -> str:
    return os.getenv(env_name, default).strip() or default


def _login_rate_limit() -> str:
    return _configured_rate_limit('AUTH_LOGIN_RATE_LIMIT', '10 per minute')


def _register_rate_limit() -> str:
    return _configured_rate_limit('AUTH_REGISTER_RATE_LIMIT', '5 per hour')


def _oauth_start_rate_limit() -> str:
    return _configured_rate_limit('AUTH_OAUTH_START_RATE_LIMIT', '20 per minute')


def _oauth_callback_rate_limit() -> str:
    return _configured_rate_limit('AUTH_OAUTH_CALLBACK_RATE_LIMIT', '20 per minute')


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _legacy_password_fallback_disabled() -> bool:
    return _env_flag('OPENMYND_DISABLE_LEGACY_PASSWORD_FALLBACK', default=False)


def _oauth_scope(provider_id: str) -> str:
    # Keep the sign-in grant minimal. Additional Google People API access should
    # be requested later as an explicit account/profile enrichment action, not on
    # every login.
    if provider_id == 'google':
        return ' '.join(GOOGLE_SIGN_IN_SCOPES)
    return 'openid email profile'


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
        'display_name': 'NULL',
        'last_name': 'NULL',
        'password_auth_enabled': '1',
        'onboarding_completed': '1',
        'registered_at': 'NULL',
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
@limiter.limit(_oauth_start_rate_limit)
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
        'scope': _oauth_scope(provider_id),
        'state': state,
    }
    if provider_id == 'google':
        auth_params['include_granted_scopes'] = 'true'
    return redirect(f"{_oauth_endpoint(config, 'authorization_endpoint')}?{urlencode(auth_params)}")


@auth_bp.route('/oauth/<provider_id>/callback', methods=['GET'])
@limiter.limit(_oauth_callback_rate_limit)
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
        provider_profile = _exchange_oauth_profile(
            config,
            code,
            extended_profile=bool(state.get('extended_profile')),
        )
        user_id, created_user = _get_or_create_oauth_user(provider_id, provider_profile)
    except Exception as exc:
        current_app.logger.warning('OAuth callback failed for %s: %s', provider_id, exc)
        return _redirect_oauth_error('External sign-in failed. Please try again.')

    access_token = create_access_token(identity=str(user_id))
    with get_db() as conn:
        user = _load_user_for_auth(conn, user_id)
    if not user:
        return _redirect_oauth_error('OpenMynd account could not be loaded.')
    auth_user = _serialise_auth_user(user)
    onboarding_required = created_user or auth_user.get('onboarding_completed') is False
    if onboarding_required:
        auth_user['onboarding_completed'] = False
    current_app.logger.info(
        'OAuth callback completed: provider=%s user_id=%s created=%s onboarding_required=%s',
        provider_id,
        user_id,
        created_user,
        onboarding_required,
    )
    return _redirect_oauth_success(
        access_token,
        auth_user,
        str(state.get('return_url') or '/dashboard'),
        onboarding_required=onboarding_required,
    )


@auth_bp.route('/register', methods=['POST'])
@limiter.limit(_register_rate_limit)
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

            user_columns = _database_adapter().table_columns(conn, 'users')
            insert_columns = ['username', 'password', 'first_name', 'last_name']
            insert_values = [
                username,
                password_hash.decode('utf-8'),
                first_name,
                last_name,
            ]
            registered_at = _utc_timestamp()
            if 'registered_at' in user_columns:
                insert_columns.append('registered_at')
                insert_values.append(registered_at)
            placeholders = ', '.join('?' for _ in insert_columns)
            cursor = conn.execute(
                _sql(append_returning_id(
                    f'''
                    INSERT INTO users ({', '.join(insert_columns)})
                    VALUES ({placeholders})
                    ''',
                    _database_provider(),
                )),
                tuple(insert_values),
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
                'password_auth_enabled': True,
                'onboarding_completed': True,
                'registered_at': registered_at if 'registered_at' in user_columns else None,
            }
        }), 201
        
    except Exception as exc:
        if _is_duplicate_username_error(exc):
            return jsonify({'error': 'Username already exists'}), 409
        raise

@auth_bp.route('/login', methods=['POST'])
@limiter.limit(_login_rate_limit)
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
        if _legacy_password_fallback_disabled():
            current_app.logger.warning(
                'Legacy password fallback blocked for user_id=%s',
                user['id'],
            )
            return jsonify({'error': 'Invalid credentials'}), 401
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
    for name in required_env:
        value = os.getenv(name, '').strip()
        normalised_value = value.lower()
        if not value or any(normalised_value.startswith(prefix) for prefix in OAUTH_PLACEHOLDER_PREFIXES):
            return False
    return True


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


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _redirect_oauth_error(message: str):
    params = urlencode({'error': message})
    return redirect(f'{_frontend_base_url()}/oauth/callback?{params}')


def _redirect_oauth_success(
    token: str,
    user: dict[str, object],
    return_url: str,
    *,
    onboarding_required: bool = False,
):
    encoded_user = base64.urlsafe_b64encode(
        jsonify(user).get_data()
    ).decode('ascii').rstrip('=')
    fragment = urlencode({
        'token': token,
        'user': encoded_user,
        'returnUrl': '/dashboard' if onboarding_required else _safe_return_url(return_url),
        'onboardingRequired': 'true' if onboarding_required else 'false',
    })
    callback_path = 'onboarding' if onboarding_required else 'oauth/callback'
    return redirect(f'{_frontend_base_url()}/{callback_path}#{fragment}')


def _exchange_oauth_profile(
    config: dict[str, str],
    code: str,
    *,
    extended_profile: bool = False,
) -> dict[str, object]:
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
    if config.get('env_prefix') == 'GOOGLE' and extended_profile:
        profile.update(_fetch_google_people_profile(access_token))
    return profile


def _fetch_google_people_profile(access_token: str) -> dict[str, object]:
    if not _env_flag('OAUTH_GOOGLE_EXTENDED_PROFILE', default=False):
        return {}

    try:
        response = httpx.get(
            'https://people.googleapis.com/v1/people/me',
            params={'personFields': 'birthdays,genders,locales,photos'},
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=12,
        )
        response.raise_for_status()
        person = response.json()
    except Exception as exc:  # noqa: BLE001
        current_app.logger.info('Google extended profile lookup skipped: %s', exc)
        return {}

    enriched: dict[str, object] = {}
    age = _age_from_google_birthdays(person.get('birthdays'))
    if age is not None:
        enriched['age'] = age
    gender = _gender_from_google_genders(person.get('genders'))
    if gender:
        enriched['gender'] = gender
    locale = _locale_from_google_locales(person.get('locales'))
    if locale:
        enriched['locale'] = locale
    picture_url = _photo_url_from_google_photos(person.get('photos'))
    if picture_url:
        enriched['picture'] = picture_url
    return enriched


def _age_from_google_birthdays(birthdays: object) -> int | None:
    if not isinstance(birthdays, list):
        return None
    today = date.today()
    for birthday in birthdays:
        value = birthday.get('date') if isinstance(birthday, dict) else None
        if not isinstance(value, dict):
            continue
        year = value.get('year')
        month = value.get('month')
        day = value.get('day')
        if not all(isinstance(part, int) for part in (year, month, day)):
            continue
        try:
            born = date(int(year), int(month), int(day))
        except ValueError:
            continue
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age if 0 <= age <= 130 else None
    return None


def _gender_from_google_genders(genders: object) -> str:
    if not isinstance(genders, list) or not genders:
        return ''
    value = str(genders[0].get('value') if isinstance(genders[0], dict) else '').strip().lower()
    return {
        'male': 'man',
        'female': 'woman',
        'other': 'other / prefer not to say',
        'unknown': 'other / prefer not to say',
    }.get(value, '')


def _locale_from_google_locales(locales: object) -> str:
    if not isinstance(locales, list) or not locales:
        return ''
    return str(locales[0].get('value') if isinstance(locales[0], dict) else '').strip()


def _photo_url_from_google_photos(photos: object) -> str:
    if not isinstance(photos, list):
        return ''
    for photo in photos:
        url = str(photo.get('url') if isinstance(photo, dict) else '').strip()
        if url.startswith('https://'):
            return url
    return ''


def _get_or_create_oauth_user(provider_id: str, profile: dict[str, object]) -> tuple[int, bool]:
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
            _sync_oauth_user_profile(conn, user_id, profile)
            return user_id, False

        username = _unique_oauth_username(conn, provider_id, email, display_name, provider_subject)
        password_hash = bcrypt.hashpw(secrets.token_urlsafe(32).encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_columns = _database_adapter().table_columns(conn, 'users')
        insert_columns = ['username', 'password', 'first_name', 'last_name']
        insert_values = [username, password_hash, first_name, last_name]
        if 'display_name' in user_columns:
            insert_columns.append('display_name')
            insert_values.append(_safe_display_name(first_name or display_name))
        if 'password_auth_enabled' in user_columns:
            insert_columns.append('password_auth_enabled')
            insert_values.append(0)
        if 'onboarding_completed' in user_columns:
            insert_columns.append('onboarding_completed')
            insert_values.append(0)
        if 'registered_at' in user_columns:
            insert_columns.append('registered_at')
            insert_values.append(_utc_timestamp())
        placeholders = ', '.join('?' for _ in insert_columns)
        cursor = conn.execute(
            _sql(append_returning_id(
                f'''
                INSERT INTO users ({', '.join(insert_columns)})
                VALUES ({placeholders})
                ''',
                _database_provider(),
            )),
            tuple(insert_values),
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
        _sync_oauth_user_profile(conn, user_id, profile)
        return user_id, True


def _sync_oauth_user_profile(conn, user_id: int, profile: dict[str, object]) -> None:
    user_columns = _database_adapter().table_columns(conn, 'users')
    candidate_columns = {
        'first_name',
        'last_name',
        'display_name',
        'age',
        'gender',
        'profile_picture_storage_key',
    }
    select_columns = [column for column in candidate_columns if column in user_columns]
    if not select_columns:
        return

    current_user = conn.execute(
        _sql(f"SELECT {', '.join(select_columns)} FROM users WHERE id = ?"),
        (user_id,),
    ).fetchone()
    if not current_user:
        return

    first_name = _safe_name_part(profile.get('given_name'))
    last_name = _safe_name_part(profile.get('family_name'))
    display_name = _safe_display_name(first_name or profile.get('name'))
    age = profile.get('age') if isinstance(profile.get('age'), int) else None
    gender = str(profile.get('gender') or '').strip()
    profile_picture_storage_key = _oauth_profile_picture_storage_key(
        user_id,
        str(profile.get('picture') or '').strip(),
        str(current_user['profile_picture_storage_key'] or '')
        if 'profile_picture_storage_key' in select_columns
        else '',
    )

    proposed_values = {
        'first_name': first_name,
        'last_name': last_name,
        'display_name': display_name,
        'age': age,
        'gender': gender,
        'profile_picture_storage_key': profile_picture_storage_key,
    }
    updates: list[str] = []
    values: list[object] = []
    for column, proposed_value in proposed_values.items():
        if column not in select_columns or proposed_value in {None, ''}:
            continue
        current_value = current_user[column]
        if current_value not in {None, ''}:
            continue
        updates.append(f'{column} = ?')
        values.append(proposed_value)

    if updates:
        values.append(user_id)
        conn.execute(
            _sql(f"UPDATE users SET {', '.join(updates)} WHERE id = ?"),
            tuple(values),
        )


def _oauth_profile_picture_storage_key(
    user_id: int,
    picture_url: str,
    current_storage_key: str,
) -> str:
    if current_storage_key or not _safe_google_profile_image_url(picture_url):
        return ''
    try:
        response = httpx.get(picture_url, timeout=12, follow_redirects=True)
        response.raise_for_status()
        content_type = str(response.headers.get('content-type') or '').split(';')[0].lower()
        if content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            return ''
        image_bytes = response.content
        if not image_bytes or len(image_bytes) > MAX_OAUTH_PROFILE_IMAGE_BYTES:
            return ''
        normalised_image = _normalise_oauth_profile_picture(image_bytes)
        return store_profile_image(normalised_image, user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.info('OAuth profile picture import skipped: %s', exc)
        return ''


def _safe_google_profile_image_url(picture_url: str) -> bool:
    if not picture_url:
        return False
    parsed = urlparse(picture_url)
    if parsed.scheme != 'https':
        return False
    return parsed.hostname in {
        'lh3.googleusercontent.com',
        'lh4.googleusercontent.com',
        'lh5.googleusercontent.com',
        'lh6.googleusercontent.com',
        'googleusercontent.com',
    } or str(parsed.hostname or '').endswith('.googleusercontent.com')


def _normalise_oauth_profile_picture(image_bytes: bytes) -> bytes:
    try:
        image = Image.open(BytesIO(image_bytes))
    except UnidentifiedImageError as exc:
        raise ValueError('OAuth profile picture was not a readable image') from exc

    if image.mode in ('RGBA', 'LA'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1])
        image = background
    else:
        image = image.convert('RGB')

    image = ImageOps.fit(
        image,
        PROFILE_IMAGE_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    output = BytesIO()
    image.save(output, format='JPEG', quality=PROFILE_IMAGE_JPEG_QUALITY, optimize=True)
    return output.getvalue()


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


def _safe_display_name(raw: object) -> str:
    value = str(raw or '').strip()
    if not value:
        return ''
    first_part = value.split()[0][:8].strip()
    return first_part if re.fullmatch(r"^[A-Za-z][A-Za-z '\-]{0,7}$", first_part) else ''


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
        'last_name': user['last_name'],
        'display_name': user['display_name'],
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
        'password_auth_enabled': bool(user['password_auth_enabled']),
        'onboarding_completed': bool(user['onboarding_completed']),
        'registered_at': user['registered_at'],
    }

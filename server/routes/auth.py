# Authentication routes with JWT
from flask import Blueprint, request, jsonify, current_app, redirect
from flask_jwt_extended import (
    create_access_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
import bcrypt
import base64
import hashlib
import hmac
import json
from io import BytesIO
import sqlite3
import re
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.parse import urlparse

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from PIL import Image, ImageOps, UnidentifiedImageError
from extensions import limiter
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.email_delivery import send_transactional_email
from services.auth_sessions import (
    epoch_to_utc_iso,
    record_auth_session,
    revoke_session_by_jti,
)
from services.admin_bootstrap import ensure_bootstrap_admin_for_user
from services.legacy_passwords import bcrypt_password, password_is_bcrypt_hash
from services.media_storage import resolve_image_url, store_profile_image
from services.security_audit import record_security_event
from services.sql_compat import adapt_placeholders, append_returning_id, inserted_id

auth_bp = Blueprint('auth', __name__)

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128
MAX_USERNAME_LENGTH = 32
MAX_NAME_LENGTH = 12
MAX_OAUTH_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_SIZE = (400, 400)
PROFILE_IMAGE_JPEG_QUALITY = 88
EMAIL_VERIFICATION_EXPIRY_HOURS = 24
PASSWORD_RESET_EXPIRY_MINUTES = 60
USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')
NAME_PATTERN = re.compile(r"^[A-Za-z]+(?:[ '-][A-Za-z]+)*$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
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


def _password_reset_rate_limit() -> str:
    return _configured_rate_limit('AUTH_PASSWORD_RESET_RATE_LIMIT', '5 per hour')


def _email_verification_rate_limit() -> str:
    return _configured_rate_limit('AUTH_EMAIL_VERIFICATION_RATE_LIMIT', '5 per hour')


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


def _registration_email_required() -> bool:
    return _env_flag('OPENMYND_REQUIRE_REGISTRATION_EMAIL', default=False)


def _cookie_auth_enabled() -> bool:
    return bool(current_app.config.get('OPENMYND_AUTH_COOKIE_MODE'))


def _attach_auth_cookie(response, access_token: str):
    if _cookie_auth_enabled():
        set_access_cookies(response, access_token)
    return response


def _auth_json_response(payload: dict[str, object], access_token: str, status_code: int = 200):
    response = jsonify(payload)
    response.status_code = status_code
    return _attach_auth_cookie(response, access_token)


def _create_tracked_access_token(user_id: int) -> str:
    access_token = create_access_token(identity=str(user_id))
    decoded_token = decode_token(access_token)
    jwt_jti = str(decoded_token.get('jti') or '').strip()
    if not jwt_jti:
        raise RuntimeError('JWT token did not include a jti claim')
    with get_db() as conn:
        record_auth_session(
            conn,
            user_id=int(user_id),
            jwt_jti=jwt_jti,
            expires_at=epoch_to_utc_iso(decoded_token.get('exp')),
        )
    return access_token


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


def _normalise_email(raw: object) -> str:
    email = str(raw or '').strip().lower()
    if not email:
        return ''
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        return ''
    return email


def _validate_registration_payload(
    username: str,
    password: str,
    first_name: str,
    last_name: str,
    email: str,
) -> str | None:
    if not username or not password:
        return 'Username and password required'
    if _registration_email_required() and not email:
        return 'A valid email address is required'
    if len(username) < 3:
        return 'Username must be at least 3 characters'
    if len(username) > MAX_USERNAME_LENGTH:
        return 'Username must be 32 characters or fewer'
    if not USERNAME_PATTERN.fullmatch(username):
        return 'Username may only contain letters, numbers, dots, underscores, and hyphens'
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        return 'Password must be between 8 and 128 characters'
    password_error = _validate_password(password)
    if password_error:
        return password_error
    if len(first_name) > MAX_NAME_LENGTH or len(last_name) > MAX_NAME_LENGTH:
        return 'First and last name must be 12 characters or fewer'
    if first_name and not NAME_PATTERN.fullmatch(first_name):
        return 'First name contains unsupported characters'
    if last_name and not NAME_PATTERN.fullmatch(last_name):
        return 'Last name contains unsupported characters'
    return None


def _validate_password(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        return 'Password must be between 8 and 128 characters'
    if password.isdigit():
        return 'Password cannot be only numbers'
    if not any(char.isalpha() for char in password):
        return 'Password must include at least one letter'
    if not any(char.isdigit() for char in password):
        return 'Password must include at least one number'
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


def _audit_security_event(
    conn,
    event_type: str,
    *,
    user_id: int | None = None,
    outcome: str = 'success',
    metadata: dict[str, object] | None = None,
) -> bool:
    return record_security_event(
        conn,
        database_provider=_database_provider(),
        secret=current_app.config.get('JWT_SECRET_KEY', ''),
        user_id=user_id,
        event_type=event_type,
        outcome=outcome,
        request_obj=request,
        metadata=metadata,
        logger=current_app.logger,
    )


def _audit_security_event_for_request(
    event_type: str,
    *,
    user_id: int | None = None,
    outcome: str = 'success',
    metadata: dict[str, object] | None = None,
) -> bool:
    try:
        with get_db() as conn:
            return _audit_security_event(
                conn,
                event_type,
                user_id=user_id,
                outcome=outcome,
                metadata=metadata,
            )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning('Security audit connection could not be opened: %s', exc)
        return False


def _optional_user_selects(conn) -> str:
    columns = _database_adapter().table_columns(conn, 'users')
    optional_columns = {
        'profile_picture_storage_key': 'NULL',
        'email': 'NULL',
        'email_verified': '0',
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
        'account_status': "'active'",
        'registered_at': 'NULL',
    }
    selects = []
    for column_name, fallback in optional_columns.items():
        if column_name in columns:
            selects.append(column_name)
        else:
            selects.append(f'{fallback} AS {column_name}')
    return ', '.join(selects)


def _account_is_restricted(user) -> bool:
    return str(user['account_status'] or 'active').strip().lower() == 'restricted'


def _restricted_account_response():
    return jsonify({
        'error': 'This account has been restricted. Contact the OpenMynd administrator for access.',
        'code': 'account_restricted',
    }), 403


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
        _audit_security_event_for_request(
            'oauth_callback_failed',
            outcome='rejected',
            metadata={'provider': provider_id, 'reason': 'provider_exchange'},
        )
        return _redirect_oauth_error('External sign-in failed. Please try again.')

    with get_db() as conn:
        user = _load_user_for_auth(conn, user_id)
        ensure_bootstrap_admin_for_user(conn, user, current_app.logger)
    if not user:
        _audit_security_event_for_request(
            'oauth_callback_failed',
            user_id=int(user_id),
            outcome='rejected',
            metadata={'provider': provider_id, 'reason': 'user_load'},
        )
        return _redirect_oauth_error('OpenMynd account could not be loaded.')
    if _account_is_restricted(user):
        _audit_security_event_for_request(
            'oauth_callback_failed',
            user_id=int(user_id),
            outcome='rejected',
            metadata={'provider': provider_id, 'reason': 'account_restricted'},
        )
        return _redirect_oauth_error(
            'This account has been restricted. Contact the OpenMynd administrator for access.'
        )
    access_token = _create_tracked_access_token(int(user_id))
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
    with get_db() as conn:
        _audit_security_event(
            conn,
            'oauth_callback_success',
            user_id=int(user_id),
            metadata={
                'provider': provider_id,
                'created_user': bool(created_user),
                'onboarding_required': bool(onboarding_required),
            },
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
    email = _normalise_email(data.get('email'))
    first_name = _normalise_optional_name(data.get('first_name'))
    last_name = _normalise_optional_name(data.get('last_name'))

    validation_error = _validate_registration_payload(
        username, password, first_name, last_name, email
    )
    if validation_error:
        _audit_security_event_for_request(
            'register_failed',
            outcome='rejected',
            metadata={'reason': 'validation'},
        )
        return jsonify({'error': validation_error}), 400
    
    # Hash password with bcrypt
    password_hash = bcrypt_password(password)
    
    try:
        with get_db() as conn:
            existing_user = conn.execute(
                _sql('SELECT id FROM users WHERE username = ?'),
                (username,),
            ).fetchone()
            if existing_user:
                _audit_security_event(
                    conn,
                    'register_failed',
                    outcome='rejected',
                    metadata={'reason': 'duplicate_username'},
                )
                return jsonify({'error': 'Username already exists'}), 409
            email_columns = _database_adapter().table_columns(conn, 'users')
            if email and 'email' in email_columns:
                existing_email = conn.execute(
                    _sql('SELECT id FROM users WHERE lower(email) = lower(?)'),
                    (email,),
                ).fetchone()
                if existing_email:
                    _audit_security_event(
                        conn,
                        'register_failed',
                        outcome='rejected',
                        metadata={'reason': 'duplicate_email'},
                    )
                    return jsonify({'error': 'Email is already registered'}), 409

            user_columns = _database_adapter().table_columns(conn, 'users')
            insert_columns = ['username', 'password', 'first_name', 'last_name']
            insert_values = [
                username,
                password_hash,
                first_name,
                last_name,
            ]
            if 'email' in user_columns:
                insert_columns.append('email')
                insert_values.append(email)
            if 'email_verified' in user_columns:
                insert_columns.append('email_verified')
                insert_values.append(0)
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
            _audit_security_event(conn, 'register_success', user_id=int(user_id))
            _send_email_verification(conn, int(user_id), email)
        
        # Create JWT token
        access_token = _create_tracked_access_token(int(user_id))
        
        return _auth_json_response({
            'token': access_token,
            'user': {
                'id': user_id,
                'username': username,
                'email': email,
                'email_verified': False,
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
                'account_status': 'active',
                'registered_at': registered_at if 'registered_at' in user_columns else None,
            }
        }, access_token, 201)
        
    except Exception as exc:
        if _is_duplicate_username_error(exc):
            _audit_security_event_for_request(
                'register_failed',
                outcome='rejected',
                metadata={'reason': 'duplicate_username'},
            )
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
        _audit_security_event_for_request(
            'login_failed',
            outcome='rejected',
            metadata={'reason': 'missing_credentials'},
        )
        return jsonify({'error': 'Username and password required'}), 400
    
    with get_db() as conn:
        optional_user_selects = _optional_user_selects(conn)
        user = conn.execute(
            _sql(f'''SELECT id, username, password, first_name, {optional_user_selects}
                FROM users WHERE username = ?'''),
            (username,)
        ).fetchone()
    
    if not user:
        _audit_security_event_for_request(
            'login_failed',
            outcome='rejected',
            metadata={'reason': 'unknown_user'},
        )
        return jsonify({'error': 'Invalid credentials'}), 401

    # Check password (handle both bcrypt and legacy plaintext)
    stored_password = user['password'] or ''
    if password_is_bcrypt_hash(stored_password):
        try:
            password_matches = bcrypt.checkpw(
                password.encode('utf-8'),
                stored_password.encode('utf-8'),
            )
        except ValueError:
            password_matches = False
        if not password_matches:
            _audit_security_event_for_request(
                'login_failed',
                user_id=int(user['id']),
                outcome='rejected',
                metadata={'reason': 'bad_password'},
            )
            return jsonify({'error': 'Invalid credentials'}), 401
    else:  # Legacy plaintext (should be migrated)
        if _legacy_password_fallback_disabled():
            current_app.logger.warning(
                'Legacy password fallback blocked for user_id=%s',
                user['id'],
            )
            _audit_security_event_for_request(
                'login_failed',
                user_id=int(user['id']),
                outcome='rejected',
                metadata={'reason': 'legacy_password_disabled'},
            )
            return jsonify({'error': 'Invalid credentials'}), 401
        if password != stored_password:
            _audit_security_event_for_request(
                'login_failed',
                user_id=int(user['id']),
                outcome='rejected',
                metadata={'reason': 'bad_password'},
            )
            return jsonify({'error': 'Invalid credentials'}), 401
        # Migrate legacy plaintext password to bcrypt on successful login.
        password_hash = bcrypt_password(password)
        with get_db() as conn:
            conn.execute(
                _sql('UPDATE users SET password = ? WHERE id = ?'),
                (password_hash, user['id']),
            )
            _audit_security_event(
                conn,
                'legacy_password_migrated',
                user_id=int(user['id']),
            )
    
    if _account_is_restricted(user):
        _audit_security_event_for_request(
            'login_failed',
            user_id=int(user['id']),
            outcome='rejected',
            metadata={'reason': 'account_restricted'},
        )
        return _restricted_account_response()

    # Create JWT token
    access_token = _create_tracked_access_token(int(user['id']))
    _audit_security_event_for_request('login_success', user_id=int(user['id']))
    with get_db() as conn:
        ensure_bootstrap_admin_for_user(conn, user, current_app.logger)
    
    return _auth_json_response({
        'token': access_token,
        'user': _serialise_auth_user(user),
    }, access_token, 200)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Clear cookie auth state when cookie mode is enabled."""
    try:
        verify_jwt_in_request(optional=True)
        jwt_payload = get_jwt()
        jwt_jti = str(jwt_payload.get('jti') or '').strip()
    except Exception:
        jwt_jti = ''

    if jwt_jti:
        try:
            with get_db() as conn:
                revoke_session_by_jti(conn, jwt_jti, reason='logout')
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning('Logout session revocation failed: %s', exc)

    response = jsonify({'message': 'Logged out'})
    unset_jwt_cookies(response)
    return response, 200


@auth_bp.route('/auth/email/verification/request', methods=['POST'])
@limiter.limit(_email_verification_rate_limit)
@jwt_required()
def request_email_verification():
    """Send a verification email for the authenticated password account."""
    user_id = int(get_jwt_identity())
    with get_db() as conn:
        user = conn.execute(
            _sql('SELECT id, email, email_verified FROM users WHERE id = ?'),
            (user_id,),
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if not user['email']:
            return jsonify({'error': 'No email address is saved for this account'}), 400
        if bool(user['email_verified']):
            return jsonify({'message': 'Email is already verified'}), 200
        _send_email_verification(conn, user_id, str(user['email']))

    return jsonify({'message': 'Verification email sent if delivery is configured'}), 202


@auth_bp.route('/auth/email/verification/confirm', methods=['POST'])
def confirm_email_verification():
    """Verify an email address using a one-time token."""
    data = request.get_json() or {}
    token = str(data.get('token') or '').strip()
    with get_db() as conn:
        token_row = _consume_account_security_token(
            conn,
            purpose='email_verification',
            token=token,
        )
        if not token_row:
            _audit_security_event(
                conn,
                'email_verification_failed',
                outcome='rejected',
                metadata={'reason': 'invalid_token'},
            )
            return jsonify({'error': 'Verification link is invalid or expired'}), 400
        user_id = int(token_row['user_id'])
        conn.execute(
            _sql('UPDATE users SET email_verified = 1 WHERE id = ?'),
            (user_id,),
        )
        _audit_security_event(conn, 'email_verified', user_id=user_id)

    return jsonify({'message': 'Email verified'}), 200


@auth_bp.route('/auth/password-reset/request', methods=['POST'])
@limiter.limit(_password_reset_rate_limit)
def request_password_reset():
    """Request a password reset email without disclosing account existence."""
    data = request.get_json() or {}
    email = _normalise_email(data.get('email'))
    generic_response = {
        'message': 'If an account exists for that email, a reset link has been sent.'
    }
    if not email:
        return jsonify(generic_response), 202

    with get_db() as conn:
        user = conn.execute(
            _sql(
                '''
                SELECT id, email, password_auth_enabled
                FROM users
                WHERE lower(email) = lower(?)
                '''
            ),
            (email,),
        ).fetchone()
        if user and bool(user['password_auth_enabled']):
            _send_password_reset(conn, int(user['id']), str(user['email']))
        else:
            _audit_security_event(
                conn,
                'password_reset_failed',
                outcome='rejected',
                metadata={'reason': 'unknown_or_oauth_only'},
            )

    return jsonify(generic_response), 202


@auth_bp.route('/auth/password-reset/confirm', methods=['POST'])
def confirm_password_reset():
    """Set a new password using a valid reset token."""
    data = request.get_json() or {}
    token = str(data.get('token') or '').strip()
    new_password = str(data.get('password') or '')
    password_error = _validate_password(new_password)
    if password_error:
        return jsonify({'error': password_error}), 400

    with get_db() as conn:
        token_row = _consume_account_security_token(
            conn,
            purpose='password_reset',
            token=token,
        )
        if not token_row:
            _audit_security_event(
                conn,
                'password_reset_failed',
                outcome='rejected',
                metadata={'reason': 'invalid_token'},
            )
            return jsonify({'error': 'Reset link is invalid or expired'}), 400
        user_id = int(token_row['user_id'])
        password_hash = bcrypt_password(new_password)
        conn.execute(
            _sql(
                '''
                UPDATE users
                SET password = ?, password_auth_enabled = 1
                WHERE id = ?
                '''
            ),
            (password_hash, user_id),
        )
        _audit_security_event(conn, 'password_reset_success', user_id=user_id)

    return jsonify({'message': 'Password reset'}), 200


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


def _token_hash(token: str) -> str:
    secret = current_app.config.get('JWT_SECRET_KEY', '')
    return hmac.new(
        str(secret or 'openmynd-token').encode('utf-8'),
        token.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _create_account_security_token(
    conn,
    *,
    user_id: int,
    purpose: str,
    expires_at: datetime,
) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute(
        _sql(
            '''
            INSERT INTO account_security_tokens (
                user_id, purpose, token_hash, expires_at
            ) VALUES (?, ?, ?, ?)
            '''
        ),
        (
            user_id,
            purpose,
            _token_hash(token),
            expires_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
        ),
    )
    return token


def _consume_account_security_token(conn, *, purpose: str, token: str):
    token = str(token or '').strip()
    if not token:
        return None
    row = conn.execute(
        _sql(
            '''
            SELECT id, user_id, expires_at, consumed_at
            FROM account_security_tokens
            WHERE purpose = ? AND token_hash = ?
            '''
        ),
        (purpose, _token_hash(token)),
    ).fetchone()
    if not row or row['consumed_at']:
        return None
    try:
        expires_at = datetime.strptime(str(row['expires_at']), '%Y-%m-%dT%H:%M:%SZ').replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    if expires_at < datetime.now(timezone.utc):
        return None
    conn.execute(
        _sql('UPDATE account_security_tokens SET consumed_at = ? WHERE id = ?'),
        (_utc_timestamp(), row['id']),
    )
    return row


def _verification_url(token: str) -> str:
    return f'{_frontend_base_url()}/verify-email?token={token}'


def _password_reset_url(token: str) -> str:
    return f'{_frontend_base_url()}/reset-password?token={token}'


def _send_email_verification(conn, user_id: int, email: str) -> bool:
    if not email:
        return False
    try:
        token = _create_account_security_token(
            conn,
            user_id=user_id,
            purpose='email_verification',
            expires_at=datetime.now(timezone.utc) + timedelta(hours=EMAIL_VERIFICATION_EXPIRY_HOURS),
        )
        send_transactional_email(
            to_address=email,
            subject='Verify your OpenMynd email',
            text_body=(
                'Verify your OpenMynd email address using this link:\n\n'
                f'{_verification_url(token)}\n\n'
                f'This link expires in {EMAIL_VERIFICATION_EXPIRY_HOURS} hours.'
            ),
            logger=current_app.logger,
        )
        _audit_security_event(
            conn,
            'email_verification_requested',
            user_id=user_id,
            metadata={'delivery_provider': os.getenv('EMAIL_PROVIDER') or 'console'},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning('Email verification send failed: %s', exc)
        _audit_security_event(
            conn,
            'email_verification_failed',
            user_id=user_id,
            outcome='rejected',
            metadata={'reason': 'delivery_failed'},
        )
        return False


def _send_password_reset(conn, user_id: int, email: str) -> bool:
    if not email:
        return False
    try:
        token = _create_account_security_token(
            conn,
            user_id=user_id,
            purpose='password_reset',
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_EXPIRY_MINUTES),
        )
        send_transactional_email(
            to_address=email,
            subject='Reset your OpenMynd password',
            text_body=(
                'Reset your OpenMynd password using this link:\n\n'
                f'{_password_reset_url(token)}\n\n'
                f'This link expires in {PASSWORD_RESET_EXPIRY_MINUTES} minutes.'
            ),
            logger=current_app.logger,
        )
        _audit_security_event(
            conn,
            'password_reset_requested',
            user_id=user_id,
            metadata={'delivery_provider': os.getenv('EMAIL_PROVIDER') or 'console'},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning('Password reset send failed: %s', exc)
        _audit_security_event(
            conn,
            'password_reset_failed',
            user_id=user_id,
            outcome='rejected',
            metadata={'reason': 'delivery_failed'},
        )
        return False


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
        json.dumps(user, separators=(',', ':')).encode('utf-8')
    ).decode('ascii').rstrip('=')
    fragment = urlencode({
        'token': token,
        'user': encoded_user,
        'returnUrl': '/dashboard' if onboarding_required else _safe_return_url(return_url),
        'onboardingRequired': 'true' if onboarding_required else 'false',
    })
    callback_path = 'onboarding' if onboarding_required else 'oauth/callback'
    response = redirect(f'{_frontend_base_url()}/{callback_path}#{fragment}')
    return _attach_auth_cookie(response, token)


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
        password_hash = bcrypt_password(secrets.token_urlsafe(32))
        user_columns = _database_adapter().table_columns(conn, 'users')
        insert_columns = ['username', 'password', 'first_name', 'last_name']
        insert_values = [username, password_hash, first_name, last_name]
        if 'email' in user_columns:
            insert_columns.append('email')
            insert_values.append(email)
        if 'email_verified' in user_columns:
            insert_columns.append('email_verified')
            insert_values.append(1 if email_verified else 0)
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
        'email',
        'email_verified',
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
        'email': str(profile.get('email') or profile.get('preferred_username') or '').strip().lower(),
        'email_verified': 1 if bool(profile.get('email_verified')) else None,
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
        'email': user['email'],
        'email_verified': bool(user['email_verified']),
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
        'account_status': user['account_status'] or 'active',
        'registered_at': user['registered_at'],
    }

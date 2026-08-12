# server/routes/profile.py
# Profile management routes
from io import BytesIO

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import bcrypt
import os
import re
from PIL import Image, ImageOps, UnidentifiedImageError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from extensions import limiter
from services.account_deletion import (
    collect_user_media_storage_keys,
    delete_user_account_data,
    delete_user_media,
)
from services.ai_config import ALLOWED_ANALYSIS_MODELS
from services.auth_sessions import revoke_user_sessions
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.media_storage import (
    delete_image,
    resolve_image_url,
    store_profile_image,
)
from services.security_audit import record_security_event
from services.sql_compat import adapt_placeholders

profile_bp = Blueprint('profile', __name__)

MAX_SHORT_TEXT_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 24
MAX_CUSTOM_GUIDANCE_LENGTH = 100
MAX_TIMEZONE_LENGTH = 64
MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024
PROFILE_IMAGE_SIZE = (400, 400)
PROFILE_IMAGE_JPEG_QUALITY = 88
MAX_PROFILE_IMAGE_PIXELS = 40_000_000
HOLIDAY_COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")
TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DISPLAY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,23}$")
CUSTOM_GUIDANCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ,.?!'\"()&/\-:]{0,99}$")
CODE_LIKE_PATTERN = re.compile(r"[<>{}\\[\\]`;]|javascript:|script|onerror|onclick", re.IGNORECASE)
ALLOWED_REMINDER_DAYS = {
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
}
ALLOWED_REMINDER_ENTRY_TYPES = {
    'daily',
    'dream',
    'thought_record',
}
ALLOWED_PRONOUNS = {
    'he/him',
    'she/her',
    'they/them',
    'he/they',
    'she/they',
    'prefer not to say',
}
ALLOWED_GENDERS = {
    'man',
    'woman',
    'non-binary',
    'agender',
    'other / prefer not to say',
}
ALLOWED_AI_TONES = {'friendly', 'empathetic', 'analytical', 'formal'}
ALLOWED_AI_VERBOSITY = {'concise', 'balanced', 'detailed'}
ALLOWED_AI_FOCUS = {
    'reflective',
    'emotional-support',
    'practical-advice',
    'creative-prompts',
}
ALLOWED_AI_MODELS = set(ALLOWED_ANALYSIS_MODELS)
ACCOUNT_DELETE_CONFIRMATION = 'DELETE MY ACCOUNT'


def _configured_rate_limit(env_name: str, default: str) -> str:
    return os.getenv(env_name, default).strip() or default


def _account_delete_rate_limit() -> str:
    return _configured_rate_limit('ACCOUNT_DELETE_RATE_LIMIT', '5 per hour')


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


def get_db():
    """Get database connection."""
    return _database_adapter().connect(timeout=10)


def _normalise_optional_text(value, *, max_length: int):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return ''
    if len(text) > max_length:
        raise ValueError(f'Maximum length is {max_length} characters')
    return text


def _normalise_choice(value, *, allowed: set[str], field_label: str):
    if value is None:
        return None

    normalised = str(value).strip()
    if not normalised:
        return ''
    if normalised not in allowed:
        raise ValueError(f'Invalid {field_label}')
    return normalised


def _normalise_display_name(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return ''
    if len(text) > MAX_DISPLAY_NAME_LENGTH:
        raise ValueError(f'Display name must be {MAX_DISPLAY_NAME_LENGTH} characters or fewer')
    if not DISPLAY_NAME_PATTERN.fullmatch(text):
        raise ValueError(
            'Display name may only use letters, numbers, hyphens, and underscores'
        )
    return text


def _normalise_custom_guidance(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return ''
    if len(text) > MAX_CUSTOM_GUIDANCE_LENGTH:
        raise ValueError(
            f'Custom guidance must be {MAX_CUSTOM_GUIDANCE_LENGTH} characters or fewer'
        )
    if CODE_LIKE_PATTERN.search(text) or not CUSTOM_GUIDANCE_PATTERN.fullmatch(text):
        raise ValueError(
            'Custom guidance must be plain text only; code or script-like text is not allowed'
        )
    return text


def _normalise_timezone(value):
    timezone_name = _normalise_optional_text(value, max_length=MAX_TIMEZONE_LENGTH)
    if timezone_name in {None, ''}:
        return timezone_name

    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError('Timezone must be a valid IANA timezone') from exc
    return timezone_name


def _normalise_reminder_days(value):
    if value is None:
        return None

    if isinstance(value, list):
        raw_days = value
    else:
        raw_days = str(value).split(',')

    normalised_days = []
    for raw_day in raw_days:
        day = str(raw_day).strip().lower()
        if not day:
            continue
        if day not in ALLOWED_REMINDER_DAYS:
            raise ValueError('Reminder days must be valid weekdays')
        if day not in normalised_days:
            normalised_days.append(day)

    return ','.join(normalised_days)


def _normalise_reminder_entry_types(value):
    if value is None:
        return None

    if isinstance(value, list):
        raw_types = value
    else:
        raw_types = str(value).split(',')

    normalised_types = []
    for raw_type in raw_types:
        entry_type = str(raw_type).strip().lower().replace('-', '_')
        if not entry_type:
            continue
        if entry_type not in ALLOWED_REMINDER_ENTRY_TYPES:
            raise ValueError('Reminder entry types must be valid record types')
        if entry_type not in normalised_types:
            normalised_types.append(entry_type)

    return ','.join(normalised_types)


def _normalise_reminder_time(value):
    if value is None:
        return None

    normalised = str(value).strip()
    if not normalised:
        return ''
    if not TIME_PATTERN.fullmatch(normalised):
        raise ValueError('Reminder time must use HH:MM format')
    return normalised


def _normalise_reminder_silence_days(value):
    if value is None:
        return None

    try:
        silence_days = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Reminder silence days must be a number') from exc
    if silence_days < 1 or silence_days > 30:
        raise ValueError('Reminder silence days must be between 1 and 30')
    return silence_days


def _normalise_weekly_goal(value):
    if value is None:
        return None

    try:
        weekly_goal = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('Weekly writing goal must be a number') from exc
    if weekly_goal < 1 or weekly_goal > 21:
        raise ValueError('Weekly writing goal must be between 1 and 21')
    return weekly_goal


def _normalise_profile_update(field: str, value):
    if field in {'first_name', 'last_name',
                 'chatgpt_daily_diary_coachname', 'chatgpt_dream_diary_coachname'}:
        return _normalise_optional_text(value, max_length=MAX_SHORT_TEXT_LENGTH)
    if field == 'pronouns':
        return _normalise_choice(value, allowed=ALLOWED_PRONOUNS, field_label='pronouns')
    if field == 'gender':
        return _normalise_choice(value, allowed=ALLOWED_GENDERS, field_label='gender')
    if field == 'display_name':
        return _normalise_display_name(value)
    if field == 'custom_guidance':
        return _normalise_custom_guidance(value)
    if field == 'timezone':
        return _normalise_timezone(value)
    if field == 'holiday_country_code':
        if value is None:
            return None
        normalised = str(value).strip().upper()
        if not normalised:
            return ''
        if not HOLIDAY_COUNTRY_CODE_PATTERN.fullmatch(normalised):
            raise ValueError('Holiday country must use a two-letter country code')
        return normalised
    if field == 'show_public_holidays':
        return 1 if bool(value) else 0
    if field == 'show_on_this_day':
        return 1 if bool(value) else 0
    if field == 'onboarding_completed':
        return 1 if bool(value) else 0
    if field == 'ai_tone':
        return _normalise_choice(value, allowed=ALLOWED_AI_TONES, field_label='AI tone')
    if field == 'ai_verbosity':
        return _normalise_choice(
            value, allowed=ALLOWED_AI_VERBOSITY, field_label='AI verbosity'
        )
    if field == 'ai_focus':
        return _normalise_choice(value, allowed=ALLOWED_AI_FOCUS, field_label='AI focus')
    if field == 'ai_model':
        return _normalise_choice(value, allowed=ALLOWED_AI_MODELS, field_label='AI model')
    if field == 'allow_ai_history':
        return 1 if bool(value) else 0
    if field == 'allow_ai_attachment_context':
        return 1 if bool(value) else 0
    if field == 'writing_reminders_enabled':
        return 1 if bool(value) else 0
    if field == 'writing_reminder_days':
        return _normalise_reminder_days(value)
    if field == 'writing_reminder_time':
        return _normalise_reminder_time(value)
    if field == 'writing_reminder_silence_days':
        return _normalise_reminder_silence_days(value)
    if field == 'writing_reminder_entry_types':
        return _normalise_reminder_entry_types(value)
    if field == 'writing_rhythm_progress_enabled':
        return 1 if bool(value) else 0
    if field == 'writing_rhythm_weekly_goal':
        return _normalise_weekly_goal(value)
    if field == 'chat_enabled':
        return 1 if bool(value) else 0

    return value


def _normalise_profile_picture(file_bytes: bytes) -> bytes:
    if not file_bytes:
        raise ValueError('No image was selected')

    try:
        image = Image.open(BytesIO(file_bytes))
        image_format = image.format
        if image.width * image.height > MAX_PROFILE_IMAGE_PIXELS:
            raise ValueError('Profile image dimensions are too large')
        image = ImageOps.exif_transpose(image)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Choose a valid JPEG, PNG, or WebP image') from exc

    if image_format not in {'JPEG', 'PNG', 'WEBP'}:
        raise ValueError('Choose a JPEG, PNG, or WebP image')

    if image.mode not in {'RGB', 'L'}:
        source = image.convert('RGBA')
        background = Image.new('RGB', source.size, (255, 255, 255))
        background.paste(source, mask=source.split()[-1])
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


def _profile_payload(user) -> dict:
    payload = dict(user)
    storage_key = payload.pop('profile_picture_storage_key', None)
    payload['profile_picture_url'] = resolve_image_url(storage_key)
    if payload.get('email') == '':
        payload['email'] = None
    for field in (
        'show_public_holidays',
        'show_on_this_day',
        'allow_ai_history',
        'allow_ai_attachment_context',
        'writing_reminders_enabled',
        'writing_rhythm_progress_enabled',
        'chat_enabled',
        'email_verified',
        'password_auth_enabled',
        'onboarding_completed',
    ):
        if field in payload and payload[field] is not None:
            payload[field] = bool(payload[field])
    return payload


def _select_profile(conn, user_id: int):
    auth_table_exists = _database_adapter().table_exists(conn, 'auth_identities')
    oauth_email_select = (
        "(SELECT email FROM auth_identities WHERE user_id = users.id ORDER BY id LIMIT 1)"
        if auth_table_exists
        else "NULL"
    )
    oauth_email_verified_select = (
        "(SELECT email_verified FROM auth_identities WHERE user_id = users.id ORDER BY id LIMIT 1)"
        if auth_table_exists
        else "NULL"
    )
    auth_provider_select = (
        "(SELECT provider FROM auth_identities WHERE user_id = users.id ORDER BY id LIMIT 1)"
        if auth_table_exists
        else "NULL"
    )
    return conn.execute(_sql(f'''
        SELECT id, username,
               COALESCE(users.email, {oauth_email_select}) AS email,
               CASE
                   WHEN users.email_verified = 1 THEN 1
                   WHEN {oauth_email_verified_select} = 1 THEN 1
                   ELSE 0
               END AS email_verified,
               first_name, last_name, age, sex, goals,
               dailydiary_api_key, dreamdiary_api_key,
               chatgpt_daily_diary_coachname, chatgpt_dream_diary_coachname,
               registered_at,
               display_name, pronouns, gender, custom_guidance, timezone,
               holiday_country_code, show_public_holidays, show_on_this_day,
               ai_tone, ai_verbosity,
               ai_focus, ai_model, allow_ai_history, allow_ai_attachment_context,
               writing_reminders_enabled, writing_reminder_days, writing_reminder_time,
               writing_reminder_silence_days, writing_reminder_entry_types,
               writing_rhythm_progress_enabled, writing_rhythm_weekly_goal,
               chat_enabled, password_auth_enabled, onboarding_completed,
               {('account_status' if 'account_status' in _database_adapter().table_columns(conn, 'users') else "'active'")} AS account_status,
               {auth_provider_select} AS auth_provider,
               profile_picture_storage_key
        FROM users WHERE users.id = ?
    '''), (user_id,)).fetchone()

@profile_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile."""
    user_id = int(get_jwt_identity())
    
    with get_db() as conn:
        user = _select_profile(conn, user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(_profile_payload(user)), 200

@profile_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Update user profile."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    # Build update query dynamically
    allowed_fields = [
        'first_name', 'last_name', 'age', 'sex', 'goals',
        'dailydiary_api_key', 'dreamdiary_api_key',
        'chatgpt_daily_diary_coachname', 'chatgpt_dream_diary_coachname',
        'display_name', 'pronouns', 'gender', 'custom_guidance',
        'timezone', 'holiday_country_code', 'show_public_holidays', 'show_on_this_day',
        'ai_tone', 'ai_verbosity',
        'ai_focus', 'ai_model', 'allow_ai_history', 'allow_ai_attachment_context',
        'writing_reminders_enabled', 'writing_reminder_days', 'writing_reminder_time',
        'writing_reminder_silence_days', 'writing_reminder_entry_types',
        'writing_rhythm_progress_enabled', 'writing_rhythm_weekly_goal',
        'chat_enabled', 'onboarding_completed'
    ]
    
    updates = []
    values = []
    
    try:
        for field in allowed_fields:
            if field in data:
                updates.append(f'{field} = ?')
                values.append(_normalise_profile_update(field, data[field]))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(user_id)
    
    with get_db() as conn:
        conn.execute(_sql(f'''
            UPDATE users
            SET {', '.join(updates)}
            WHERE id = ?
        '''), values)
        updated_user = _select_profile(conn, user_id)
    
    return jsonify({'message': 'Profile updated', 'user': _profile_payload(updated_user)}), 200


@profile_bp.route('/profile/picture', methods=['POST'])
@jwt_required()
def upload_profile_picture():
    """Replace the current user's profile picture with a normalised square image."""
    user_id = int(get_jwt_identity())
    uploaded_file = request.files.get('image')
    if uploaded_file is None:
        return jsonify({'error': 'Choose an image to upload'}), 400

    file_bytes = uploaded_file.read(MAX_PROFILE_IMAGE_BYTES + 1)
    if len(file_bytes) > MAX_PROFILE_IMAGE_BYTES:
        return jsonify({'error': 'Profile images must be 5 MB or smaller'}), 413

    try:
        image_bytes = _normalise_profile_picture(file_bytes)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    old_storage_key = None
    new_storage_key = None
    with get_db() as conn:
        current_user = _select_profile(conn, user_id)
    if current_user is None:
        return jsonify({'error': 'User not found'}), 404

    old_storage_key = current_user['profile_picture_storage_key']
    new_storage_key = store_profile_image(image_bytes, user_id=user_id)
    try:
        with get_db() as conn:
            conn.execute(
                _sql('UPDATE users SET profile_picture_storage_key = ? WHERE id = ?'),
                (new_storage_key, user_id),
            )
            updated_user = _select_profile(conn, user_id)
    except Exception:
        delete_image(new_storage_key)
        raise

    delete_image(old_storage_key)
    return jsonify({
        'message': 'Profile picture updated',
        'user': _profile_payload(updated_user),
    }), 200


@profile_bp.route('/profile/picture', methods=['DELETE'])
@jwt_required()
def delete_profile_picture():
    """Remove the current user's profile picture without changing profile data."""
    user_id = int(get_jwt_identity())
    with get_db() as conn:
        current_user = _select_profile(conn, user_id)
        if current_user is None:
            return jsonify({'error': 'User not found'}), 404

        old_storage_key = current_user['profile_picture_storage_key']
        conn.execute(
            _sql('UPDATE users SET profile_picture_storage_key = NULL WHERE id = ?'),
            (user_id,),
        )
        updated_user = _select_profile(conn, user_id)

    delete_image(old_storage_key)
    return jsonify({
        'message': 'Profile picture removed',
        'user': _profile_payload(updated_user),
    }), 200


@profile_bp.route('/profile/account', methods=['DELETE'])
@limiter.limit(_account_delete_rate_limit)
@jwt_required()
def delete_account():
    """Permanently delete the authenticated user's account and app-owned data."""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    password = str(data.get('password') or '')
    confirmation = str(data.get('confirmation') or '').strip()

    if confirmation != ACCOUNT_DELETE_CONFIRMATION:
        _audit_security_event_for_request(
            'account_delete_failed',
            user_id=user_id,
            outcome='rejected',
            metadata={'reason': 'confirmation'},
        )
        return jsonify({
            'error': f'Type {ACCOUNT_DELETE_CONFIRMATION} to confirm account deletion.'
        }), 400

    with get_db() as conn:
        user = conn.execute(
            _sql('SELECT id, password, password_auth_enabled FROM users WHERE id = ?'),
            (user_id,),
        ).fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if bool(user['password_auth_enabled']):
            if not password:
                _audit_security_event(
                    conn,
                    'account_delete_failed',
                    user_id=user_id,
                    outcome='rejected',
                    metadata={'reason': 'password_required'},
                )
                return jsonify({'error': 'Password is required to delete your account.'}), 400
            if not _password_matches(password, user['password']):
                _audit_security_event(
                    conn,
                    'account_delete_failed',
                    user_id=user_id,
                    outcome='rejected',
                    metadata={'reason': 'bad_password'},
                )
                return jsonify({'error': 'Password did not match.'}), 400

        _audit_security_event(conn, 'account_delete_requested', user_id=user_id)
        revoke_user_sessions(conn, user_id, reason='account_deleted')
        media_storage_keys = collect_user_media_storage_keys(conn, user_id)
        delete_user_account_data(conn, user_id)
        _audit_security_event(
            conn,
            'account_delete_success',
            metadata={'user_rows_removed': True},
        )

    delete_user_media(media_storage_keys)
    return jsonify({'message': 'Account deleted'}), 200


def _password_matches(password: str, stored_password: str) -> bool:
    if stored_password.startswith('$2b$'):
        return bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8'))
    return password == stored_password

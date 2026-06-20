# server/routes/profile.py
# Profile management routes
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
import re

profile_bp = Blueprint('profile', __name__)

MAX_SHORT_TEXT_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 8
MAX_CUSTOM_GUIDANCE_LENGTH = 100
MAX_TIMEZONE_LENGTH = 64
DISPLAY_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,7}$")
CUSTOM_GUIDANCE_PATTERN = re.compile(r"^[A-Za-z0-9 ,.?!'\"()&/\-:]{1,100}$")
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
ALLOWED_AI_MODELS = {'gpt-4o-mini', 'gpt-4.1-mini', 'gpt-4.1'}

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Profile get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


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
        raise ValueError("Display name may only use letters, spaces, apostrophes, and hyphens")
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
    if not CUSTOM_GUIDANCE_PATTERN.fullmatch(text):
        raise ValueError(
            'Custom guidance may only use plain text, numbers, spaces, and basic punctuation'
        )
    return text


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
        return _normalise_optional_text(value, max_length=MAX_TIMEZONE_LENGTH)
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

    return value

@profile_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    user = cursor.execute('''
        SELECT id, username, first_name, last_name, age, sex, goals,
               dailydiary_api_key, dreamdiary_api_key,
               chatgpt_daily_diary_coachname, chatgpt_dream_diary_coachname,
               display_name, pronouns, gender, custom_guidance, timezone, ai_tone, ai_verbosity,
               ai_focus, ai_model, allow_ai_history, allow_ai_attachment_context
        FROM users WHERE id = ?
    ''', (user_id,)).fetchone()
    
    conn.close()
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify(dict(user)), 200

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
        'timezone', 'ai_tone', 'ai_verbosity',
        'ai_focus', 'ai_model', 'allow_ai_history', 'allow_ai_attachment_context'
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
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(f'''
        UPDATE users
        SET {', '.join(updates)}
        WHERE id = ?
    ''', values)

    conn.commit()

    updated_user = cursor.execute('''
        SELECT id, username, first_name, last_name, age, sex, goals,
               dailydiary_api_key, dreamdiary_api_key,
               chatgpt_daily_diary_coachname, chatgpt_dream_diary_coachname,
               display_name, pronouns, gender, custom_guidance, timezone, ai_tone, ai_verbosity,
               ai_focus, ai_model, allow_ai_history, allow_ai_attachment_context
        FROM users WHERE id = ?
    ''', (user_id,)).fetchone()

    conn.close()
    
    return jsonify({'message': 'Profile updated', 'user': dict(updated_user)}), 200

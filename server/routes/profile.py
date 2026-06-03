# server/routes/profile.py
# Profile management routes
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3

profile_bp = Blueprint('profile', __name__)

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Profile get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

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
               display_name, pronouns, timezone, ai_tone, ai_verbosity,
               ai_focus, allow_ai_history
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
        'display_name', 'pronouns', 'timezone', 'ai_tone', 'ai_verbosity',
        'ai_focus', 'allow_ai_history'
    ]
    
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            value = data[field]
            if field == 'allow_ai_history':
                value = 1 if bool(value) else 0
            values.append(value)
    
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
               display_name, pronouns, timezone, ai_tone, ai_verbosity,
               ai_focus, allow_ai_history
        FROM users WHERE id = ?
    ''', (user_id,)).fetchone()

    conn.close()
    
    return jsonify({'message': 'Profile updated', 'user': dict(updated_user)}), 200

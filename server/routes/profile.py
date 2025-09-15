# server/routes/profile.py
# Profile management routes
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
import os

profile_bp = Blueprint('profile', __name__)

def get_db():
    """Get database connection."""
    db_path = os.getenv('DB_PATH', './app.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@profile_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile."""
    user_id = get_jwt_identity()
    
    conn = get_db()
    cursor = conn.cursor()
    
    user = cursor.execute('''
        SELECT id, username, first_name, last_name, age, sex, goals,
               dailydiary_api_key, dreamdiary_api_key,
               chatgpt_daily_diary_coachname, chatgpt_dream_diary_coachname
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
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Build update query dynamically
    allowed_fields = [
        'first_name', 'last_name', 'age', 'sex', 'goals',
        'dailydiary_api_key', 'dreamdiary_api_key',
        'chatgpt_daily_diary_coachname', 'chatgpt_dream_diary_coachname'
    ]
    
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(data[field])
    
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
    conn.close()
    
    return jsonify({'message': 'Profile updated'}), 200
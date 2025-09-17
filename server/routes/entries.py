# server/routes/entries.py
# CRUD routes for diary entries
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
from datetime import datetime

entries_bp = Blueprint('entries', __name__)

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Entries get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Daily entries endpoints
@entries_bp.route('/daily', methods=['GET'])
@jwt_required()
def get_daily_entries():
    """Get all daily entries for authenticated user."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entries = cursor.execute('''
        SELECT * FROM dailydiary_entries
        WHERE user_id = ?
        ORDER BY entry_date DESC, entry_number DESC
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    return jsonify([dict(entry) for entry in entries]), 200

@entries_bp.route('/daily/<int:entry_id>', methods=['GET'])
@jwt_required()
def get_daily_entry(entry_id):
    """Get specific daily entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entry = cursor.execute('''
        SELECT * FROM dailydiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id)).fetchone()
    
    conn.close()
    
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    
    return jsonify(dict(entry)), 200

@entries_bp.route('/daily', methods=['POST'])
@jwt_required()
def create_daily_entry():
    """Create new daily entry."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    entry_date = data.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
    user_message = data.get('user_message', '')
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get next entry number for the day
    max_entry = cursor.execute('''
        SELECT MAX(entry_number) as max_num
        FROM dailydiary_entries
        WHERE user_id = ? AND entry_date = ?
    ''', (user_id, entry_date)).fetchone()
    
    entry_number = (max_entry['max_num'] or 0) + 1
    
    cursor.execute('''
        INSERT INTO dailydiary_entries 
        (user_id, entry_date, entry_number, user_message, tags)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, entry_date, entry_number, user_message, data.get('tags', '')))
    
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    
    return jsonify({
        'id': entry_id,
        'entry_date': entry_date,
        'entry_number': entry_number
    }), 201

@entries_bp.route('/daily/<int:entry_id>', methods=['PUT'])
@jwt_required()
def update_daily_entry(entry_id):
    """Update daily entry with AI analysis results."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check ownership
    entry = cursor.execute(
        'SELECT id FROM dailydiary_entries WHERE id = ? AND user_id = ?',
        (entry_id, user_id)
    ).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404
    
    # Update allowed fields
    allowed_fields = ['user_message', 'ai_response', 'daily_people_names', 'tags']
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(data[field])
    
    if not updates:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(entry_id)
    values.append(user_id)
    
    cursor.execute(f'''
        UPDATE dailydiary_entries
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
    ''', values)
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Entry updated'}), 200

@entries_bp.route('/daily/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_daily_entry(entry_id):
    """Delete daily entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM dailydiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id))
    
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({'error': 'Entry not found'}), 404
    
    return '', 204

# Dream entries endpoints
@entries_bp.route('/dreams', methods=['GET'])
@jwt_required()
def get_dream_entries():
    """Get all dream entries for authenticated user."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entries = cursor.execute('''
        SELECT * FROM dreamdiary_entries
        WHERE user_id = ?
        ORDER BY entry_date DESC, entry_number DESC
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    return jsonify([dict(entry) for entry in entries]), 200

@entries_bp.route('/dreams/<int:entry_id>', methods=['GET'])
@jwt_required()
def get_dream_entry(entry_id):
    """Get specific dream entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entry = cursor.execute('''
        SELECT * FROM dreamdiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id)).fetchone()
    
    conn.close()
    
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    
    return jsonify(dict(entry)), 200

@entries_bp.route('/dreams', methods=['POST'])
@jwt_required()
def create_dream_entry():
    """Create new dream entry."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    entry_date = data.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get next entry number for the day
    max_entry = cursor.execute('''
        SELECT MAX(entry_number) as max_num
        FROM dreamdiary_entries
        WHERE user_id = ? AND entry_date = ?
    ''', (user_id, entry_date)).fetchone()
    
    entry_number = (max_entry['max_num'] or 0) + 1
    
    # Insert with all dream-specific fields
    cursor.execute('''
        INSERT INTO dreamdiary_entries 
        (user_id, entry_date, entry_number, title, cast, location, 
         period, emotion, plot, symbols_and_imagery, insight, action, other, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, entry_date, entry_number,
        data.get('title', ''),
        data.get('cast', ''),
        data.get('location', ''),
        data.get('period', ''),
        data.get('emotion', ''),
        data.get('plot', ''),
        data.get('symbols_and_imagery', ''),
        data.get('insight', ''),
        data.get('action', ''),
        data.get('other', ''),
        data.get('tags', '')
    ))
    
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    
    return jsonify({
        'id': entry_id,
        'entry_date': entry_date,
        'entry_number': entry_number
    }), 201

@entries_bp.route('/dreams/<int:entry_id>', methods=['PUT'])
@jwt_required()
def update_dream_entry(entry_id):
    """Update dream entry with AI analysis results."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check ownership
    entry = cursor.execute(
        'SELECT id FROM dreamdiary_entries WHERE id = ? AND user_id = ?',
        (entry_id, user_id)
    ).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404
    
    # Update allowed fields
    allowed_fields = [
        'title', 'cast', 'location', 'period', 'emotion', 'plot',
        'symbols_and_imagery', 'insight', 'action', 'other',
        'summary', 'interpretation', 'image_prompt', 'image_url',
        'dream_people_names', 'tags'
    ]
    
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(data[field])
    
    if not updates:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(entry_id)
    values.append(user_id)
    
    cursor.execute(f'''
        UPDATE dreamdiary_entries
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
    ''', values)
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Entry updated'}), 200

@entries_bp.route('/dreams/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_dream_entry(entry_id):
    """Delete dream entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM dreamdiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id))
    
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({'error': 'Entry not found'}), 404
    
    return '', 204

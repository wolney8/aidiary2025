# server/routes/entries.py
# CRUD routes for diary entries
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
from datetime import datetime
import re
from html import escape

entries_bp = Blueprint('entries', __name__)

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Entries get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_entry_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, '%Y-%m-%d')
        except ValueError:
            return None


def _format_date_strings(date_obj):
    if not date_obj:
        return []
    return [
        date_obj.strftime('%d/%m/%Y'),
        date_obj.strftime('%A %d %B %Y'),
        date_obj.strftime('%d %B %Y'),
        date_obj.strftime('%B %Y'),
        date_obj.strftime('%B')
    ]


def _highlight_text(source: str, term: str, context: int = 60) -> str | None:
    if not source:
        return None
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    match = pattern.search(source)
    if not match:
        return None

    start = max(match.start() - context, 0)
    end = min(match.end() + context, len(source))
    excerpt = source[start:end]
    escaped = escape(excerpt)
    escaped_term = escape(term)
    escaped_pattern = re.compile(re.escape(escaped_term), re.IGNORECASE)
    highlighted = escaped_pattern.sub(lambda m: f'<span class="match">{m.group(0)}</span>', escaped)
    if start > 0:
        highlighted = '…' + highlighted
    if end < len(source):
        highlighted = highlighted + '…'
    return highlighted


def _highlight_inline(source: str, term: str) -> str | None:
    if not source:
        return None
    escaped = escape(source)
    escaped_term = escape(term)
    pattern = re.compile(re.escape(escaped_term), re.IGNORECASE)
    if not pattern.search(escaped):
        return None
    return pattern.sub(lambda m: f'<span class="match">{m.group(0)}</span>', escaped)

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


@entries_bp.route('/search', methods=['GET'])
@jwt_required()
def search_entries():
    """Search diary entries by content, tags, AI response, and metadata."""
    user_id = int(get_jwt_identity())
    query = (request.args.get('q') or '').strip()
    filters_param = (request.args.get('filters') or '').strip()

    if not query:
        return jsonify({
            'query': query,
            'filters': [],
            'filters_display': 'All Entries',
            'results': []
        }), 200

    filter_tokens = [token.strip().lower() for token in filters_param.split(',') if token.strip()]
    valid_filters = {'tags', 'date', 'keywords', 'people'}
    active_filters = {token for token in filter_tokens if token in valid_filters}
    include_all = not active_filters

    filter_labels = {
        'tags': 'Tags',
        'date': 'Date',
        'keywords': 'Keywords',
        'people': "People's Names"
    }
    filters_display = 'All Entries' if include_all else ', '.join(filter_labels[f] for f in active_filters)

    conn = get_db()
    cursor = conn.cursor()

    daily_rows = cursor.execute('''
        SELECT id, entry_date, user_message, ai_response, tags, daily_people_names
        FROM dailydiary_entries
        WHERE user_id = ?
    ''', (user_id,)).fetchall()

    dream_rows = cursor.execute('''
        SELECT id, entry_date, title, plot, interpretation, tags, dream_people_names
        FROM dreamdiary_entries
        WHERE user_id = ?
    ''', (user_id,)).fetchall()

    conn.close()

    results = []
    term = query.lower()

    def field_enabled(field_name: str) -> bool:
        if include_all:
            return True
        mapping = {
            'body': None,
            'ai': 'keywords',
            'tags': 'tags',
            'people': 'people',
            'date': 'date'
        }
        mapped = mapping.get(field_name)
        if mapped is None:
            return include_all
        return mapped in active_filters

    def process_entry(entry_type: str, base_data: dict) -> None:
        text_body = base_data.get('body') or ''
        ai_text = base_data.get('ai') or ''
        tags_text = base_data.get('tags') or ''
        people_text = base_data.get('people') or ''
        entry_date_obj = base_data.get('date_obj')
        entry_date_iso = base_data.get('entry_date')
        title_plain = base_data.get('title_plain') or ''

        matches = {}
        matched = False

        if field_enabled('body'):
            highlighted = _highlight_text(text_body, query)
            if highlighted:
                matches['body'] = highlighted
                matched = True

        if field_enabled('tags') and tags_text:
            highlighted = _highlight_inline(tags_text, query)
            if highlighted:
                matches['tags'] = highlighted
                matched = True

        if field_enabled('people') and people_text:
            highlighted = _highlight_inline(people_text, query)
            if highlighted:
                matches['people'] = highlighted
                matched = True

        if field_enabled('ai') and ai_text:
            highlighted = _highlight_text(ai_text, query)
            if highlighted:
                matches['ai'] = highlighted
                matched = True

        if field_enabled('date') and entry_date_obj:
            date_strings = _format_date_strings(entry_date_obj)
            for date_str in date_strings:
                if term in date_str.lower():
                    matches['date'] = _highlight_inline(date_str, query) or escape(date_str)
                    matched = True
                    break

        if not matched:
            return

        title_highlight = _highlight_inline(title_plain, query) or escape(title_plain)
        entry_date_display = entry_date_obj.strftime('%d/%m/%Y') if entry_date_obj else ''

        results.append({
            'id': base_data['id'],
            'type': entry_type,
            'title': title_plain,
            'title_highlight': title_highlight,
            'entry_date': entry_date_iso,
            'entry_date_display': entry_date_display,
            'tags': tags_text,
            'matches': matches
        })

    for row in daily_rows:
        entry_date_obj = _parse_entry_date(row['entry_date'])
        user_message = row['user_message'] or ''
        parts = user_message.split('\n', 1)
        title_plain = parts[0].strip('" ')
        body_text = parts[1] if len(parts) > 1 else user_message
        base_data = {
            'id': row['id'],
            'entry_date': row['entry_date'],
            'date_obj': entry_date_obj,
            'title_plain': title_plain or 'Daily Entry',
            'body': user_message,
            'ai': row['ai_response'] or '',
            'tags': row['tags'] or '',
            'people': row['daily_people_names'] or ''
        }
        process_entry('daily', base_data)

    for row in dream_rows:
        entry_date_obj = _parse_entry_date(row['entry_date'])
        base_data = {
            'id': row['id'],
            'entry_date': row['entry_date'],
            'date_obj': entry_date_obj,
            'title_plain': (row['title'] or 'Dream Entry').strip('" '),
            'body': row['plot'] or '',
            'ai': row['interpretation'] or '',
            'tags': row['tags'] or '',
            'people': row['dream_people_names'] or ''
        }
        process_entry('dream', base_data)

    results.sort(key=lambda item: item['entry_date'], reverse=True)

    return jsonify({
        'query': query,
        'filters': list(active_filters),
        'filters_display': filters_display,
        'results': results
    }), 200

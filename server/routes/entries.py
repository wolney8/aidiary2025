# server/routes/entries.py
# CRUD routes for diary entries
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
from datetime import datetime
import re
from html import escape
import base64
from io import BytesIO
from services.import_service import (
    ensure_export_history_table,
    get_latest_bulk_delete_guard,
    mark_export_guard_used,
)
from services.openai_svc import OpenAIService
from PIL import Image, ImageOps, UnidentifiedImageError

entries_bp = Blueprint('entries', __name__)

ALLOWED_ENTRY_IMAGE_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}
MAX_ENTRY_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024
ENTRY_IMAGE_TARGET_SIZE = (933, 705)
ENTRY_IMAGE_JPEG_QUALITY = 85

def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Entries get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
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


def _normalise_entry_date(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            return None
    return None


def _is_future_entry_date(value: str) -> bool:
    parsed = _parse_entry_date(value)
    if not parsed:
        return False

    today = datetime.now().date()
    return parsed.date() > today


def _normalise_uploaded_entry_image(file_bytes: bytes) -> str:
    if not file_bytes:
        raise ValueError('No image data was uploaded.')

    try:
        image = Image.open(BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)
    except UnidentifiedImageError as exc:
        raise ValueError('The uploaded file is not a supported image.') from exc

    if image.mode not in ('RGB', 'L'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        alpha_source = image.convert('RGBA')
        background.paste(alpha_source, mask=alpha_source.split()[-1])
        image = background
    else:
        image = image.convert('RGB')

    cropped = ImageOps.fit(
        image,
        ENTRY_IMAGE_TARGET_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )

    output = BytesIO()
    cropped.save(
        output,
        format='JPEG',
        quality=ENTRY_IMAGE_JPEG_QUALITY,
        optimize=True,
    )
    encoded = base64.b64encode(output.getvalue()).decode('ascii')
    return f'data:image/jpeg;base64,{encoded}'


def _get_entry_range_summary(conn: sqlite3.Connection, user_id: int) -> dict[str, int | str | None | bool]:
    daily_row = conn.execute(
        'SELECT MIN(entry_date) AS min_date, MAX(entry_date) AS max_date, COUNT(*) AS total_count FROM dailydiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    dream_row = conn.execute(
        'SELECT MIN(entry_date) AS min_date, MAX(entry_date) AS max_date, COUNT(*) AS total_count FROM dreamdiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()

    all_min_dates = [value for value in [daily_row['min_date'], dream_row['min_date']] if value]
    all_max_dates = [value for value in [daily_row['max_date'], dream_row['max_date']] if value]
    daily_count = int(daily_row['total_count'] or 0)
    dream_count = int(dream_row['total_count'] or 0)

    return {
        'first_entry_date': min(all_min_dates) if all_min_dates else None,
        'last_entry_date': max(all_max_dates) if all_max_dates else None,
        'daily_count': daily_count,
        'dream_count': dream_count,
        'total_entries': daily_count + dream_count,
        'has_entries': (daily_count + dream_count) > 0,
    }


def _build_bulk_delete_readiness(
    conn: sqlite3.Connection,
    user_id: int,
    guard_token: str | None,
) -> dict[str, int | str | None | bool]:
    ensure_export_history_table(conn)
    summary = _get_entry_range_summary(conn, user_id)
    guard_record = get_latest_bulk_delete_guard(conn, user_id, guard_token)

    eligible = bool(
        summary['has_entries']
        and guard_record
        and guard_record.get('is_full_range')
        and guard_record.get('include_daily') == 1
        and guard_record.get('include_dreams') == 1
        and guard_record.get('from_date') == summary['first_entry_date']
        and guard_record.get('to_date') == summary['last_entry_date']
    )

    return {
        **summary,
        'eligible_for_delete': eligible,
        'guard_token_present': bool(guard_record),
        'requires_full_export': bool(summary['has_entries']),
    }


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
    highlighted = escaped_pattern.sub(lambda m: f'<span style="color: red; font-weight: bold;">{m.group(0)}</span>', escaped)
    if start > 0:
        highlighted = '…' + highlighted
    if end < len(source):
        highlighted = highlighted + '…'
    return highlighted


def _highlight_inline(source: str, term: str, max_length: int = 80) -> str | None:
    if not source:
        return None
    
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    match = pattern.search(source)
    if not match:
        return None
    
    # If source is short enough, just highlight and return
    if len(source) <= max_length:
        escaped = escape(source)
        escaped_term = escape(term)
        escaped_pattern = re.compile(re.escape(escaped_term), re.IGNORECASE)
        return escaped_pattern.sub(lambda m: f'<span style="color: red; font-weight: bold;">{m.group(0)}</span>', escaped)
    
    # For longer text, truncate around the match
    context = (max_length - len(term)) // 2
    start = max(match.start() - context, 0)
    end = min(match.end() + context, len(source))
    
    # Adjust to try to break at word boundaries
    if start > 0:
        space_before = source.rfind(' ', 0, start + 10)
        if space_before > start - 10:
            start = space_before + 1
    
    if end < len(source):
        space_after = source.find(' ', end - 10)
        if space_after != -1 and space_after < end + 10:
            end = space_after
    
    excerpt = source[start:end]
    escaped = escape(excerpt)
    escaped_term = escape(term)
    escaped_pattern = re.compile(re.escape(escaped_term), re.IGNORECASE)
    highlighted = escaped_pattern.sub(lambda m: f'<span style="color: red; font-weight: bold;">{m.group(0)}</span>', escaped)
    
    if start > 0:
        highlighted = '…' + highlighted
    if end < len(source):
        highlighted = highlighted + '…'
        
    return highlighted

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
    
    entry_date = _normalise_entry_date(
        data.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
    )
    if not entry_date:
        return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
    if _is_future_entry_date(entry_date):
        return jsonify({'error': 'Future entry dates are not allowed'}), 400

    user_message = data.get('user_message', '')
    title = data.get('title', '')
    
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
        (user_id, entry_date, entry_number, title, user_message, tags, daily_people_names, daily_places)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        entry_date,
        entry_number,
        title,
        user_message,
        data.get('tags', ''),
        data.get('daily_people_names', ''),
        data.get('daily_places', ''),
    ))
    
    conn.commit()
    entry_id = cursor.lastrowid
    conn.close()
    
    return jsonify({
        'id': entry_id,
        'entry_date': entry_date,
        'entry_number': entry_number,
        'title': title
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
        'SELECT id, entry_date FROM dailydiary_entries WHERE id = ? AND user_id = ?',
        (entry_id, user_id)
    ).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404
    
    # Update allowed fields
    allowed_fields = [
        'title', 'user_message', 'ai_response', 'daily_people_names', 'daily_places',
        'tags', 'mood', 'ai_style'
    ]
    updates = []
    values = []

    if 'entry_date' in data:
        parsed_entry_date = _normalise_entry_date(data.get('entry_date'))
        if not parsed_entry_date:
            conn.close()
            return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
        if _is_future_entry_date(parsed_entry_date):
            conn.close()
            return jsonify({'error': 'Future entry dates are not allowed'}), 400

        updates.append('entry_date = ?')
        values.append(parsed_entry_date)

        if parsed_entry_date != entry['entry_date']:
            max_entry = cursor.execute('''
                SELECT MAX(entry_number) as max_num
                FROM dailydiary_entries
                WHERE user_id = ? AND entry_date = ?
            ''', (user_id, parsed_entry_date)).fetchone()
            entry_number = (max_entry['max_num'] or 0) + 1
            updates.append('entry_number = ?')
            values.append(entry_number)
    
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
    
    entry_date = _normalise_entry_date(
        data.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
    )
    if not entry_date:
        return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
    if _is_future_entry_date(entry_date):
        return jsonify({'error': 'Future entry dates are not allowed'}), 400
    
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
         period, emotion, plot, symbols_and_imagery, insight, action, other, tags,
         dream_people_names, dream_places)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get('tags', ''),
        data.get('dream_people_names', ''),
        data.get('dream_places', ''),
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
        'SELECT id, entry_date FROM dreamdiary_entries WHERE id = ? AND user_id = ?',
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
        'dream_people_names', 'dream_places', 'tags', 'mood', 'ai_style'
    ]
    
    updates = []
    values = []

    if 'entry_date' in data:
        parsed_entry_date = _normalise_entry_date(data.get('entry_date'))
        if not parsed_entry_date:
            conn.close()
            return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
        if _is_future_entry_date(parsed_entry_date):
            conn.close()
            return jsonify({'error': 'Future entry dates are not allowed'}), 400

        updates.append('entry_date = ?')
        values.append(parsed_entry_date)

        if parsed_entry_date != entry['entry_date']:
            max_entry = cursor.execute('''
                SELECT MAX(entry_number) as max_num
                FROM dreamdiary_entries
                WHERE user_id = ? AND entry_date = ?
            ''', (user_id, parsed_entry_date)).fetchone()
            entry_number = (max_entry['max_num'] or 0) + 1
            updates.append('entry_number = ?')
            values.append(entry_number)
    
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


@entries_bp.route('/dreams/<int:entry_id>/generate-image', methods=['POST'])
@jwt_required()
def generate_dream_image(entry_id):
    """Generate or regenerate a dream image from the stored or overridden dream image prompt."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, recycled_image_prompt
           FROM dreamdiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    image_prompt_override = (data.get('image_prompt_override') or '').strip()
    image_prompt = image_prompt_override or (entry['image_prompt'] or '').strip()
    if not image_prompt:
        conn.close()
        return jsonify({'error': 'This dream entry does not yet have an image prompt.'}), 400

    try:
        ai_service = OpenAIService()
        image_url = ai_service.generate_image(image_prompt)
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 503
    except Exception as exc:
        current_app.logger.error('Dream image generation failed for entry %s: %s', entry_id, exc)
        conn.close()
        return jsonify({'error': 'Image generation failed'}), 502

    cursor.execute(
        'UPDATE dreamdiary_entries SET image_url = ? WHERE id = ? AND user_id = ?',
        (image_url, entry_id, user_id),
    )
    conn.commit()
    conn.close()

    return jsonify({
        'id': entry_id,
        'image_prompt': image_prompt,
        'image_url': image_url,
        'has_existing_image': bool(entry['image_url']),
        'recycled_image_prompt': (entry['recycled_image_prompt'] or ''),
    }), 200


@entries_bp.route('/dreams/<int:entry_id>/image', methods=['POST'])
@jwt_required()
def upload_dream_image(entry_id):
    """Upload or replace a dream image for the entry."""
    user_id = int(get_jwt_identity())

    if 'image' not in request.files:
        return jsonify({'error': 'Upload an image file using the "image" field.'}), 400

    uploaded_file = request.files['image']
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'No image file was selected.'}), 400

    content_type = (uploaded_file.content_type or '').lower().strip()
    if content_type not in ALLOWED_ENTRY_IMAGE_MIME_TYPES:
        return jsonify({'error': 'Unsupported image type. Use JPG, PNG, or WEBP.'}), 400

    file_bytes = uploaded_file.read()
    if len(file_bytes) > MAX_ENTRY_IMAGE_UPLOAD_BYTES:
        return jsonify({'error': 'Image is too large. Maximum size is 5 MB.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, recycled_image_prompt
           FROM dreamdiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    recycled_prompt = (
        (entry['image_prompt'] or '').strip()
        or (entry['recycled_image_prompt'] or '').strip()
    )

    try:
        image_url = _normalise_uploaded_entry_image(file_bytes)
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.error('Dream image upload failed for entry %s: %s', entry_id, exc)
        conn.close()
        return jsonify({'error': 'Image upload failed'}), 500

    cursor.execute(
        'UPDATE dreamdiary_entries SET image_url = ?, image_prompt = NULL, recycled_image_prompt = ? WHERE id = ? AND user_id = ?',
        (image_url, recycled_prompt or None, entry_id, user_id),
    )
    conn.commit()
    conn.close()

    return jsonify({
        'id': entry_id,
        'image_prompt': '',
        'image_url': image_url,
        'has_existing_image': bool(entry['image_url']),
        'recycled_image_prompt': recycled_prompt,
    }), 200


@entries_bp.route('/dreams/<int:entry_id>/image', methods=['DELETE'])
@jwt_required()
def delete_dream_image(entry_id):
    """Delete only the current dream image, preserving the stored prompt."""
    user_id = int(get_jwt_identity())

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, recycled_image_prompt
           FROM dreamdiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    restored_prompt = (
        (entry['recycled_image_prompt'] or '').strip()
        or (entry['image_prompt'] or '').strip()
    )

    cursor.execute(
        'UPDATE dreamdiary_entries SET image_url = NULL, image_prompt = ?, recycled_image_prompt = NULL WHERE id = ? AND user_id = ?',
        (restored_prompt or None, entry_id, user_id),
    )
    conn.commit()
    conn.close()

    return jsonify({
        'id': entry_id,
        'image_prompt': restored_prompt,
        'image_url': None,
        'had_existing_image': bool(entry['image_url']),
        'recycled_image_prompt': '',
    }), 200


@entries_bp.route('/entries/bulk-delete-readiness', methods=['GET'])
@jwt_required()
def get_bulk_delete_readiness():
    """Return whether the current user can bulk-delete all entries."""
    user_id = int(get_jwt_identity())
    guard_token = (request.args.get('guard_token') or '').strip() or None

    conn = get_db()
    readiness = _build_bulk_delete_readiness(conn, user_id, guard_token)
    conn.close()

    return jsonify(readiness), 200


@entries_bp.route('/entries/bulk-delete', methods=['POST'])
@jwt_required()
def bulk_delete_entries():
    """Delete all daily and dream entries for the current user after guarded export."""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    guard_token = str(data.get('guard_token') or '').strip()
    confirmation_text = str(data.get('confirmation_text') or '').strip()

    if confirmation_text != 'DELETE ALL':
        return jsonify({'error': 'Type DELETE ALL to confirm bulk delete.'}), 400

    conn = get_db()
    readiness = _build_bulk_delete_readiness(conn, user_id, guard_token)
    if not readiness['eligible_for_delete']:
        conn.close()
        return jsonify({
            'error': 'A same-session full export of all entries is required before bulk delete.',
            'readiness': readiness,
        }), 409

    guard_record = get_latest_bulk_delete_guard(conn, user_id, guard_token)
    daily_deleted = conn.execute(
        'DELETE FROM dailydiary_entries WHERE user_id = ?',
        (user_id,),
    ).rowcount
    dream_deleted = conn.execute(
        'DELETE FROM dreamdiary_entries WHERE user_id = ?',
        (user_id,),
    ).rowcount
    if guard_record:
        mark_export_guard_used(conn, int(guard_record['id']))
    else:
        conn.commit()
    conn.close()

    return jsonify({
        'message': 'All entries deleted.',
        'deleted_daily': daily_deleted,
        'deleted_dreams': dream_deleted,
        'deleted_total': daily_deleted + dream_deleted,
    }), 200


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
        SELECT id, entry_date, title, user_message, ai_response, tags, daily_people_names
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

        # Check title match (always enabled as it's core content)
        if title_plain:
            highlighted = _highlight_inline(title_plain, query)
            if highlighted:
                matches['title'] = highlighted
                matched = True

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

        # Use the title match if found, otherwise escape plain title
        title_highlight = matches.get('title') or escape(title_plain)
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
        
        # Use database title field, fallback to first line of user_message
        db_title = (row['title'] or '').strip()
        if db_title:
            title_plain = db_title
        else:
            # Fallback: use first line of user_message
            parts = user_message.split('\n', 1)
            title_plain = parts[0].strip('" ') if parts[0].strip() else 'Daily Entry'
        
        base_data = {
            'id': row['id'],
            'entry_date': row['entry_date'],
            'date_obj': entry_date_obj,
            'title_plain': title_plain,
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

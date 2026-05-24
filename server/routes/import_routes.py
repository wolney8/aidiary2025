# server/routes/import_routes.py
# Excel import endpoints — template download, file upload, import history
import io
import os
import sqlite3
import re
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from html import escape

import_bp = Blueprint('import', __name__)

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {'.xlsx', '.xls'}


def get_db():
    """Return a sqlite3 connection to the configured database."""
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_import_history_table(conn):
    """Create import_history table if it does not yet exist."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS import_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            imported_at   TEXT    NOT NULL,
            filename      TEXT    NOT NULL,
            total_rows    INTEGER NOT NULL DEFAULT 0,
            imported_count INTEGER NOT NULL DEFAULT 0,
            skipped_count  INTEGER NOT NULL DEFAULT 0,
            error_count    INTEGER NOT NULL DEFAULT 0,
            status        TEXT    NOT NULL DEFAULT 'success',
            notes         TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()


def _sanitise(value) -> str:
    """Return a plain-text, HTML-escaped string (rejects script fragments)."""
    if value is None:
        return ''
    text = str(value).strip()
    # Reject obvious script injection patterns
    if re.search(r'<\s*script', text, re.IGNORECASE):
        return ''
    return escape(text)


def _parse_entry_date(value):
    """Parse date from various string formats; return datetime or None."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y']
    for fmt in formats:
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


# ── Template Download ─────────────────────────────────────────────────────────

@import_bp.route('/import/template', methods=['GET'])
@jwt_required()
def download_template():
    """Generate and return a minimal Excel import template."""
    try:
        import openpyxl
    except ImportError:
        return jsonify({'error': 'openpyxl is not installed on the server.'}), 500

    wb = openpyxl.Workbook()

    # Daily sheet
    daily_ws = wb.active
    daily_ws.title = 'Daily Entries'
    daily_headers = ['entry_date', 'title', 'content', 'tags', 'people']
    daily_ws.append(daily_headers)
    daily_ws.append(['2025-01-15', 'Example Title', 'Today was a good day.', 'mood,work', 'Alice,Bob'])

    # Dream sheet
    dream_ws = wb.create_sheet('Dream Entries')
    dream_headers = ['entry_date', 'title', 'plot', 'cast', 'location', 'period', 'emotion',
                     'symbols_and_imagery', 'insight', 'action', 'other', 'tags']
    dream_ws.append(dream_headers)
    dream_ws.append([
        '2025-01-16', 'Flying Dream', 'I was flying over the city.',
        'Unknown figure', 'City skyline', 'Night', 'Exhilaration',
        'Wings, open sky', 'Freedom is possible', 'Journal this', '', 'dream,flight'
    ])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='ai_diary_import_template.xlsx'
    )


# ── File Upload ───────────────────────────────────────────────────────────────

@import_bp.route('/import/upload', methods=['POST'])
@jwt_required()
def upload_file():
    """Accept an Excel file and bulk-insert diary entries."""
    user_id = int(get_jwt_identity())

    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request.'}), 400

    file = request.files['file']

    if not file or not file.filename:
        return jsonify({'error': 'No file selected.'}), 400

    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': 'Invalid file type. Only .xlsx and .xls are accepted.'}), 400

    content = file.read()
    if len(content) > MAX_FILE_BYTES:
        return jsonify({'error': f'File exceeds the 5 MB limit.'}), 413
    if len(content) == 0:
        return jsonify({'error': 'Uploaded file is empty.'}), 400

    try:
        import openpyxl
        import io as _io
        wb = openpyxl.load_workbook(_io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        return jsonify({'error': 'Could not read the Excel file. Please ensure it is a valid .xlsx or .xls file.'}), 422

    imported_count = 0
    skipped_count = 0
    error_count = 0
    errors = []
    warnings = []

    conn = get_db()
    _ensure_import_history_table(conn)

    try:
        # ── Daily Entries ──
        if 'Daily Entries' in wb.sheetnames:
            ws = wb['Daily Entries']
            rows = list(ws.iter_rows(values_only=True))
            if len(rows) > 1:  # skip header row
                for row_idx, row in enumerate(rows[1:], start=2):
                    try:
                        entry_date_raw = row[0] if len(row) > 0 else None
                        title_raw      = row[1] if len(row) > 1 else None
                        content_raw    = row[2] if len(row) > 2 else None
                        tags_raw       = row[3] if len(row) > 3 else None
                        people_raw     = row[4] if len(row) > 4 else None

                        entry_date = _parse_entry_date(entry_date_raw)
                        if not entry_date:
                            errors.append(f'Daily row {row_idx}: invalid or missing date "{entry_date_raw}".')
                            error_count += 1
                            continue

                        # Duplicate check
                        existing = conn.execute(
                            'SELECT id FROM dailydiary_entries WHERE user_id=? AND entry_date=?',
                            (user_id, entry_date.strftime('%Y-%m-%d'))
                        ).fetchone()
                        if existing:
                            warnings.append(f'Daily row {row_idx}: entry for {entry_date.strftime("%d/%m/%Y")} already exists — skipped.')
                            skipped_count += 1
                            continue

                        conn.execute(
                            '''INSERT INTO dailydiary_entries
                               (user_id, entry_date, title, user_message, tags, daily_people_names)
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (
                                user_id,
                                entry_date.strftime('%Y-%m-%d'),
                                _sanitise(title_raw),
                                _sanitise(content_raw),
                                _sanitise(tags_raw),
                                _sanitise(people_raw)
                            )
                        )
                        imported_count += 1
                    except Exception:
                        errors.append(f'Daily row {row_idx}: could not be processed — please check the row data.')
                        error_count += 1

        # ── Dream Entries ──
        if 'Dream Entries' in wb.sheetnames:
            ws = wb['Dream Entries']
            rows = list(ws.iter_rows(values_only=True))
            if len(rows) > 1:
                for row_idx, row in enumerate(rows[1:], start=2):
                    try:
                        entry_date_raw = row[0] if len(row) > 0 else None
                        title_raw      = row[1] if len(row) > 1 else None
                        plot_raw       = row[2] if len(row) > 2 else None
                        cast_raw       = row[3] if len(row) > 3 else None
                        location_raw   = row[4] if len(row) > 4 else None
                        period_raw     = row[5] if len(row) > 5 else None
                        emotion_raw    = row[6] if len(row) > 6 else None
                        symbols_raw    = row[7] if len(row) > 7 else None
                        insight_raw    = row[8] if len(row) > 8 else None
                        action_raw     = row[9] if len(row) > 9 else None
                        other_raw      = row[10] if len(row) > 10 else None
                        tags_raw       = row[11] if len(row) > 11 else None

                        entry_date = _parse_entry_date(entry_date_raw)
                        if not entry_date:
                            errors.append(f'Dream row {row_idx}: invalid or missing date "{entry_date_raw}".')
                            error_count += 1
                            continue

                        existing = conn.execute(
                            'SELECT id FROM dreamdiary_entries WHERE user_id=? AND entry_date=?',
                            (user_id, entry_date.strftime('%Y-%m-%d'))
                        ).fetchone()
                        if existing:
                            warnings.append(f'Dream row {row_idx}: entry for {entry_date.strftime("%d/%m/%Y")} already exists — skipped.')
                            skipped_count += 1
                            continue

                        conn.execute(
                            '''INSERT INTO dreamdiary_entries
                               (user_id, entry_date, title, plot, cast, location, period, emotion,
                                symbols_and_imagery, insight, action, other, tags)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                user_id,
                                entry_date.strftime('%Y-%m-%d'),
                                _sanitise(title_raw),
                                _sanitise(plot_raw),
                                _sanitise(cast_raw),
                                _sanitise(location_raw),
                                _sanitise(period_raw),
                                _sanitise(emotion_raw),
                                _sanitise(symbols_raw),
                                _sanitise(insight_raw),
                                _sanitise(action_raw),
                                _sanitise(other_raw),
                                _sanitise(tags_raw)
                            )
                        )
                        imported_count += 1
                    except Exception:
                        errors.append(f'Dream row {row_idx}: could not be processed — please check the row data.')
                        error_count += 1

        conn.commit()

        # Determine overall status
        total_rows = imported_count + skipped_count + error_count
        if error_count > 0 and imported_count == 0:
            status = 'failed'
        elif error_count > 0 or skipped_count > 0:
            status = 'partial'
        else:
            status = 'success'

        # Record in import_history
        conn.execute(
            '''INSERT INTO import_history
               (user_id, imported_at, filename, total_rows, imported_count, skipped_count, error_count, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                datetime.now(timezone.utc).isoformat(),
                filename,
                total_rows,
                imported_count,
                skipped_count,
                error_count,
                status
            )
        )
        conn.commit()

    except Exception as exc:
        conn.rollback()
        current_app.logger.exception('Import upload failed: %s', exc)
        return jsonify({'error': 'Import failed due to a server error. Please try again.'}), 500
    finally:
        conn.close()

    message = (
        f'Import complete: {imported_count} entries added, '
        f'{skipped_count} skipped, {error_count} errors.'
    )

    return jsonify({
        'status': status,
        'message': message,
        'imported_count': imported_count,
        'skipped_count': skipped_count,
        'error_count': error_count,
        'errors': errors,
        'warnings': warnings
    }), 200


# ── Import History ────────────────────────────────────────────────────────────

@import_bp.route('/import/history', methods=['GET'])
@jwt_required()
def get_history():
    """Return the import history for the current user, newest first."""
    user_id = int(get_jwt_identity())
    conn = get_db()
    _ensure_import_history_table(conn)
    try:
        rows = conn.execute(
            '''SELECT id, imported_at, filename, total_rows, imported_count,
                      skipped_count, error_count, status, notes
               FROM import_history
               WHERE user_id = ?
               ORDER BY imported_at DESC
               LIMIT 50''',
            (user_id,)
        ).fetchall()
        history = [dict(row) for row in rows]
        return jsonify(history), 200
    finally:
        conn.close()

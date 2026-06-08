# server/routes/import_routes.py
# Import blueprint: file upload, history, template download, and data export
import io
import sqlite3
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.import_service import (
    DAILY_IMPORT_HEADERS,
    DREAM_IMPORT_HEADERS,
    validate_file,
    parse_excel,
    preview_import_entries,
    commit_import_preview,
    ensure_history_table,
    ensure_import_sessions_table,
    ensure_export_history_table,
    create_import_session,
    get_import_session,
    mark_import_session_consumed,
    record_import_history,
    record_export_history,
    get_import_history,
)

import_bp = Blueprint('import', __name__)


def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


# ---------------------------------------------------------------------------
# POST /api/import/upload
# ---------------------------------------------------------------------------

@import_bp.route('/import/upload', methods=['POST'])
@jwt_required()
def upload_import():
    """
    Accept an Excel workbook (.xlsx), validate it, parse entries,
    and either import immediately or stage duplicate review before commit.

    Multipart form field: ``file``

    Success response 200:
    {
      "status": "success" | "review_required",
      "summary": {
        ...
      },
      "duplicate_entries": [dict, ...],
      "import_session_id": str | null,
      "warnings": [str, ...],
      "import_id": int | null
    }

    Error response 400 / 422:
    {
      "status": "error",
      "errors": [str, ...]
    }
    """
    user_id = int(get_jwt_identity())

    # --- File presence check ---
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'errors': ['No file part in request.']}), 400

    uploaded_file = request.files['file']
    if not uploaded_file.filename:
        return jsonify({'status': 'error', 'errors': ['No file selected.']}), 400

    # Read the file bytes first so we can validate the size accurately
    file_bytes = uploaded_file.read()
    file_size = len(file_bytes)
    filename = uploaded_file.filename
    content_type = uploaded_file.content_type or ''

    # --- Structural validation ---
    errors = validate_file(filename, content_type, file_size)
    if errors:
        return jsonify({'status': 'error', 'errors': errors}), 422

    # --- Parse Excel ---
    try:
        parsed = parse_excel(file_bytes)
    except ValueError as exc:
        current_app.logger.warning('Excel parse error for user %s: %s', user_id, exc)
        return jsonify({'status': 'error', 'errors': ['The file could not be parsed. Please ensure it is a valid .xlsx workbook.']}), 422
    except RuntimeError as exc:
        # pandas / openpyxl not installed
        current_app.logger.error('Import dependency missing: %s', exc)
        return jsonify({'status': 'error', 'errors': ['Excel import is not available on this server.']}), 500

    parse_errors: list[str] = parsed.get('errors', [])
    if parse_errors:
        return jsonify({'status': 'error', 'errors': parse_errors}), 422

    parse_warnings: list[str] = parsed.get('warnings', [])

    # Reject if nothing parseable was found
    if not parsed.get('daily') and not parsed.get('dreams'):
        all_warnings = parse_warnings + ['No valid entries found in the uploaded file.']
        conn = get_db()
        ensure_history_table(conn)
        import_id = record_import_history(
            conn, user_id, filename, file_size,
            {'inserted_daily': 0, 'skipped_daily': 0,
             'inserted_dreams': 0, 'skipped_dreams': 0},
            all_warnings, status='empty',
        )
        conn.close()
        return jsonify({
            'status': 'empty',
            'summary': {
                'inserted_daily': 0,
                'skipped_daily': 0,
                'inserted_dreams': 0,
                'skipped_dreams': 0,
                'duplicate_dates_daily': [],
                'duplicate_dates_dreams': [],
            },
            'warnings': all_warnings,
            'duplicate_entries': [],
            'import_id': import_id,
        }), 200

    # --- Stage or insert entries ---
    conn = get_db()
    ensure_history_table(conn)
    ensure_import_sessions_table(conn)

    try:
        preview = preview_import_entries(conn, user_id, parsed)
    except Exception as exc:
        conn.close()
        current_app.logger.error('Import insert failed: %s', exc)
        return jsonify({'status': 'error', 'errors': ['Database error during import.']}), 500

    duplicate_rows = preview.get('duplicate_rows', [])
    public_duplicate_rows = [
        {
            'row_id': row['row_id'],
            'entry_type': row['entry_type'],
            'entry_date': row['entry_date'],
            'title': row['title'],
            'reason': row['reason'],
            'content_preview': row['content_preview'],
        }
        for row in duplicate_rows
    ]

    if duplicate_rows:
        payload = {
            'parse_warnings': parse_warnings,
            **preview,
        }
        import_session_id = create_import_session(
            conn,
            user_id=user_id,
            filename=filename,
            file_size=file_size,
            payload=payload,
        )
        conn.close()
        return jsonify({
            'status': 'review_required',
            'message': 'Duplicates found. Review and confirm before importing.',
            'summary': preview['summary'],
            'duplicate_entries': public_duplicate_rows,
            'warnings': parse_warnings,
            'errors': [],
            'import_session_id': import_session_id,
            'import_id': None,
        }), 200

    result = commit_import_preview(conn, user_id, preview, set())
    all_warnings = parse_warnings[:]
    any_inserted = result['inserted_daily'] + result['inserted_dreams'] > 0
    status_str = 'success' if any_inserted else 'skipped'
    import_id = record_import_history(
        conn, user_id, filename, file_size, result, all_warnings, status=status_str
    )
    conn.close()

    return jsonify({
        'status': status_str,
        'summary': {
            'inserted_daily': result['inserted_daily'],
            'skipped_daily': result['skipped_daily'],
            'inserted_dreams': result['inserted_dreams'],
            'skipped_dreams': result['skipped_dreams'],
            'duplicate_dates_daily': result['duplicate_dates_daily'],
            'duplicate_dates_dreams': result['duplicate_dates_dreams'],
        },
        'duplicate_entries': [],
        'warnings': all_warnings,
        'errors': [],
        'import_id': import_id,
        'import_session_id': None,
    }), 200


@import_bp.route('/import/commit', methods=['POST'])
@jwt_required()
def commit_import():
    """Commit a staged import session after duplicate review."""
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    import_session_id = payload.get('import_session_id')
    accepted_duplicate_row_ids = payload.get('accepted_duplicate_row_ids', [])

    if not isinstance(import_session_id, str) or not import_session_id.strip():
        return jsonify({'status': 'error', 'errors': ['Import session id is required.']}), 400

    if not isinstance(accepted_duplicate_row_ids, list) or any(
        not isinstance(row_id, str) for row_id in accepted_duplicate_row_ids
    ):
        return jsonify({
            'status': 'error',
            'errors': ['Accepted duplicate row ids must be an array of strings.'],
        }), 400

    conn = get_db()
    ensure_history_table(conn)
    ensure_import_sessions_table(conn)
    session = get_import_session(conn, user_id=user_id, session_id=import_session_id)
    if not session:
        conn.close()
        return jsonify({
            'status': 'error',
            'errors': ['The import review session could not be found or has already been used.'],
        }), 404

    preview_payload = session.get('payload', {})
    parse_warnings = preview_payload.get('parse_warnings', [])

    try:
        result = commit_import_preview(
            conn,
            user_id,
            preview_payload,
            set(accepted_duplicate_row_ids),
        )
        status_str = 'success'
        if result['skipped_daily'] or result['skipped_dreams']:
            status_str = 'partial' if (result['inserted_daily'] + result['inserted_dreams']) > 0 else 'skipped'

        final_warnings = list(parse_warnings)
        omitted_duplicates = result['skipped_daily'] + result['skipped_dreams']
        if omitted_duplicates:
            final_warnings.append(
                f'{omitted_duplicates} duplicate entr{"y" if omitted_duplicates == 1 else "ies"} were left out.'
            )

        import_id = record_import_history(
            conn,
            user_id,
            session['filename'],
            session['file_size_bytes'],
            result,
            final_warnings,
            status=status_str,
        )
        mark_import_session_consumed(conn, import_session_id)
    except Exception as exc:
        conn.close()
        current_app.logger.error('Import commit failed: %s', exc)
        return jsonify({'status': 'error', 'errors': ['Database error during import commit.']}), 500

    conn.close()
    return jsonify({
        'status': status_str,
        'message': 'Import successful.',
        'summary': {
            'inserted_daily': result['inserted_daily'],
            'skipped_daily': result['skipped_daily'],
            'inserted_dreams': result['inserted_dreams'],
            'skipped_dreams': result['skipped_dreams'],
            'duplicate_dates_daily': result['duplicate_dates_daily'],
            'duplicate_dates_dreams': result['duplicate_dates_dreams'],
        },
        'duplicate_entries': [],
        'warnings': final_warnings,
        'errors': [],
        'import_id': import_id,
        'import_session_id': None,
    }), 200


# ---------------------------------------------------------------------------
# GET /api/import/history
# ---------------------------------------------------------------------------

@import_bp.route('/import/history', methods=['GET'])
@jwt_required()
def get_history():
    """
    Return the import history for the authenticated user.

    Response 200:
    {
      "history": [
        {
          "id": int,
          "imported_at": "ISO-8601",
          "filename": str,
          "file_size_bytes": int,
          "inserted_daily": int,
          "skipped_daily": int,
          "inserted_dreams": int,
          "skipped_dreams": int,
          "warnings": [str, ...],
          "status": "success" | "skipped" | "empty"
        },
        ...
      ]
    }
    """
    user_id = int(get_jwt_identity())

    conn = get_db()
    ensure_history_table(conn)
    history = get_import_history(conn, user_id)
    conn.close()

    return jsonify({'history': history}), 200


# ---------------------------------------------------------------------------
# GET /api/import/template
# ---------------------------------------------------------------------------

@import_bp.route('/import/template', methods=['GET'])
@jwt_required()
def download_template():
    """
    Generate and return a blank Excel import template (.xlsx) with the
    correct sheet names and column headers for Daily and Dreams entries.
    """
    try:
        import openpyxl
    except ImportError:
        return jsonify({
            'status': 'error',
            'errors': ['openpyxl is not installed on the server.'],
        }), 500

    wb = openpyxl.Workbook()

    # --- Daily sheet ---
    ws_daily = wb.active
    ws_daily.title = 'Daily'
    ws_daily.append(list(DAILY_IMPORT_HEADERS))

    # --- Dreams sheet ---
    ws_dreams = wb.create_sheet(title='Dreams')
    ws_dreams.append(list(DREAM_IMPORT_HEADERS))

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='aidiary_import_template.xlsx',
    )


# ---------------------------------------------------------------------------
# GET /api/import/export
# ---------------------------------------------------------------------------

@import_bp.route('/import/export', methods=['GET'])
@jwt_required()
def export_entries():
    """Export the authenticated user's entries into an Excel workbook."""
    user_id = int(get_jwt_identity())

    from_date_raw = request.args.get('from_date')
    to_date_raw = request.args.get('to_date')

    include_daily_raw = request.args.get('include_daily', 'true')
    include_dreams_raw = request.args.get('include_dreams', 'true')

    include_daily = str(include_daily_raw).strip().lower() != 'false'
    include_dreams = str(include_dreams_raw).strip().lower() != 'false'

    if not include_daily and not include_dreams:
        return jsonify({
            'status': 'error',
            'errors': ['At least one export type must be selected.'],
        }), 400

    from_date = None
    to_date = None

    if from_date_raw:
        try:
            from_date = datetime.strptime(from_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'status': 'error',
                'errors': ['from_date must be in YYYY-MM-DD format.'],
            }), 400

    if to_date_raw:
        try:
            to_date = datetime.strptime(to_date_raw, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'status': 'error',
                'errors': ['to_date must be in YYYY-MM-DD format.'],
            }), 400

    if from_date and to_date and from_date > to_date:
        return jsonify({
            'status': 'error',
            'errors': ['from_date cannot be after to_date.'],
        }), 400

    try:
        import openpyxl
    except ImportError:
        return jsonify({
            'status': 'error',
            'errors': ['openpyxl is not installed on the server.'],
        }), 500

    conn = get_db()

    daily_rows = []
    dream_rows = []

    first_daily = conn.execute(
        'SELECT MIN(entry_date) AS min_date, COUNT(*) AS total_count FROM dailydiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    first_dream = conn.execute(
        'SELECT MIN(entry_date) AS min_date, COUNT(*) AS total_count FROM dreamdiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()

    overall_first_date = min(
        [value for value in [first_daily['min_date'], first_dream['min_date']] if value],
        default=None,
    )
    overall_last_daily = conn.execute(
        'SELECT MAX(entry_date) AS max_date FROM dailydiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    overall_last_dream = conn.execute(
        'SELECT MAX(entry_date) AS max_date FROM dreamdiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    overall_last_date = max(
        [value for value in [overall_last_daily['max_date'], overall_last_dream['max_date']] if value],
        default=None,
    )

    if include_daily:
        daily_query = '''
            SELECT entry_date, title, user_message, ai_response
            FROM dailydiary_entries
            WHERE user_id = ?
        '''
        daily_params = [user_id]

        if from_date:
            daily_query += ' AND entry_date >= ?'
            daily_params.append(from_date.isoformat())

        if to_date:
            daily_query += ' AND entry_date <= ?'
            daily_params.append(to_date.isoformat())

        daily_query += ' ORDER BY entry_date ASC, entry_number ASC'
        daily_rows = conn.execute(daily_query, tuple(daily_params)).fetchall()

    if include_dreams:
        dream_query = '''
            SELECT entry_date, title, plot, "cast", location, period,
                   emotion, symbols_and_imagery, insight, action, other, tags
            FROM dreamdiary_entries
            WHERE user_id = ?
        '''
        dream_params = [user_id]

        if from_date:
            dream_query += ' AND entry_date >= ?'
            dream_params.append(from_date.isoformat())

        if to_date:
            dream_query += ' AND entry_date <= ?'
            dream_params.append(to_date.isoformat())

        dream_query += ' ORDER BY entry_date ASC, entry_number ASC'
        dream_rows = conn.execute(dream_query, tuple(dream_params)).fetchall()

    wb = openpyxl.Workbook()

    if include_daily:
        ws_daily = wb.active
        ws_daily.title = 'Daily'
        ws_daily.append(list(DAILY_IMPORT_HEADERS))
        for row in daily_rows:
            ws_daily.append([
                row['entry_date'] or '',
                row['title'] or '',
                row['user_message'] or '',
                row['ai_response'] or '',
            ])

        if include_dreams:
            ws_dreams = wb.create_sheet(title='Dreams')
            ws_dreams.append(list(DREAM_IMPORT_HEADERS))
            for row in dream_rows:
                ws_dreams.append([
                    row['entry_date'] or '',
                    row['title'] or '',
                    row['plot'] or '',
                    row['cast'] or '',
                    row['location'] or '',
                    row['period'] or '',
                    row['emotion'] or '',
                    row['symbols_and_imagery'] or '',
                    row['insight'] or '',
                    row['action'] or '',
                    row['other'] or '',
                    row['tags'] or '',
                ])
    else:
        ws_dreams = wb.active
        ws_dreams.title = 'Dreams'
        ws_dreams.append(list(DREAM_IMPORT_HEADERS))
        for row in dream_rows:
            ws_dreams.append([
                row['entry_date'] or '',
                row['title'] or '',
                row['plot'] or '',
                row['cast'] or '',
                row['location'] or '',
                row['period'] or '',
                row['emotion'] or '',
                row['symbols_and_imagery'] or '',
                row['insight'] or '',
                row['action'] or '',
                row['other'] or '',
                row['tags'] or '',
            ])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    has_filters = (
        from_date is not None
        or to_date is not None
        or not include_daily
        or not include_dreams
    )
    filename = f'aidiary_export_{stamp}.xlsx'
    if has_filters:
        filename = f'aidiary_export_filtered_{stamp}.xlsx'

    ensure_export_history_table(conn)
    is_full_range = bool(
        include_daily
        and include_dreams
        and overall_first_date
        and overall_last_date
        and from_date
        and to_date
        and from_date.isoformat() == overall_first_date
        and to_date.isoformat() == overall_last_date
    )
    export_record = record_export_history(
        conn,
        user_id=user_id,
        filename=filename,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        include_daily=include_daily,
        include_dreams=include_dreams,
        daily_count=len(daily_rows),
        dream_count=len(dream_rows),
        is_full_range=is_full_range,
        issue_guard_token=is_full_range and (len(daily_rows) + len(dream_rows) > 0),
    )
    conn.close()

    response = send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )
    response.headers['Access-Control-Expose-Headers'] = 'X-AiDiary-Export-Token'
    if export_record['guard_token']:
        response.headers['X-AiDiary-Export-Token'] = export_record['guard_token']
    return response

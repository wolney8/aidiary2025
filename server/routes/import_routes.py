# server/routes/import_routes.py
# Import blueprint: file upload, history, template download, and data export
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.import_service import (
    DAILY_IMPORT_HEADERS,
    DREAM_IMPORT_HEADERS,
    validate_file,
    parse_import_file,
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
from services.media_storage import read_media_bytes

import_bp = Blueprint('import', __name__)


def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def _build_entry_asset_ref(entry_type: str, row: sqlite3.Row) -> str:
    safe_date = str(row['entry_date'] or '').replace('-', '')
    return f"{entry_type}_{safe_date}_{row['entry_number']}_{row['id']}"


def _image_filename_for_storage_key(storage_key: str | None) -> str:
    if not storage_key:
        return ''
    return storage_key.rsplit('/', 1)[-1]


def _package_attachment_filename(attachment_row: sqlite3.Row, index: int) -> str:
    base_name = _image_filename_for_storage_key(attachment_row['storage_key'])
    if not base_name:
        original_name = str(attachment_row['original_filename'] or '').strip()
        base_name = original_name.rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    if not base_name:
        base_name = f'attachment-{index}'
    return f'{index:02d}_{base_name}'


def _load_attachment_export_rows(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    entry_type: str,
    entry_ids: list[int],
) -> dict[int, list[sqlite3.Row]]:
    if not entry_ids:
        return {}

    placeholders = ','.join('?' for _ in entry_ids)
    rows = conn.execute(
        f'''
        SELECT entry_id, asset_role, storage_key, original_filename, mime_type,
               file_size_bytes, sort_order
        FROM entry_assets
        WHERE user_id = ? AND entry_type = ? AND entry_id IN ({placeholders})
        ORDER BY entry_id ASC, sort_order ASC, id ASC
        ''',
        (user_id, entry_type, *entry_ids),
    ).fetchall()

    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(int(row['entry_id']), []).append(row)
    return grouped


# ---------------------------------------------------------------------------
# POST /api/import/upload
# ---------------------------------------------------------------------------

@import_bp.route('/import/upload', methods=['POST'])
@jwt_required()
def upload_import():
    """
    Accept an Excel workbook (.xlsx) or export package (.zip), validate it, parse entries,
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

    # --- Parse workbook / package ---
    try:
        parsed = parse_import_file(file_bytes, filename=filename)
    except ValueError as exc:
        current_app.logger.warning('Excel parse error for user %s: %s', user_id, exc)
        return jsonify({'status': 'error', 'errors': ['The file could not be parsed. Please ensure it is a valid .xlsx workbook or .zip export package.']}), 422
    except RuntimeError as exc:
        # pandas / openpyxl not installed
        current_app.logger.error('Import dependency missing: %s', exc)
        return jsonify({'status': 'error', 'errors': ['Workbook import is not available on this server.']}), 500

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
            SELECT id, entry_date, entry_time, entry_number, title, user_message, ai_response,
                   image_storage_key, image_source, image_position_x, image_position_y,
                   image_prompt, recycled_image_prompt
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

        daily_query += " ORDER BY entry_date ASC, COALESCE(entry_time, '19:00') ASC, entry_number ASC"
        daily_rows = conn.execute(daily_query, tuple(daily_params)).fetchall()

    if include_dreams:
        dream_query = '''
            SELECT id, entry_date, entry_time, entry_number, title, plot, "cast", location, period,
                   emotion, symbols_and_imagery, insight, action, other, tags,
                   image_storage_key, image_source, image_position_x, image_position_y,
                   image_prompt, recycled_image_prompt
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

        dream_query += " ORDER BY entry_date ASC, COALESCE(entry_time, '08:00') ASC, entry_number ASC"
        dream_rows = conn.execute(dream_query, tuple(dream_params)).fetchall()

    wb = openpyxl.Workbook()
    daily_attachment_rows = _load_attachment_export_rows(
        conn,
        user_id=user_id,
        entry_type='daily',
        entry_ids=[int(row['id']) for row in daily_rows],
    ) if include_daily else {}
    dream_attachment_rows = _load_attachment_export_rows(
        conn,
        user_id=user_id,
        entry_type='dream',
        entry_ids=[int(row['id']) for row in dream_rows],
    ) if include_dreams else {}

    if include_daily:
        ws_daily = wb.active
        ws_daily.title = 'Daily'
        ws_daily.append(list(DAILY_IMPORT_HEADERS))
        for row in daily_rows:
            ws_daily.append([
                row['entry_date'] or '',
                row['entry_time'] or '',
                row['title'] or '',
                row['user_message'] or '',
                row['ai_response'] or '',
                '',
            ])

        if include_dreams:
            ws_dreams = wb.create_sheet(title='Dreams')
            ws_dreams.append(list(DREAM_IMPORT_HEADERS))
            for row in dream_rows:
                ws_dreams.append([
                    row['entry_date'] or '',
                    row['entry_time'] or '',
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
                    '',
                ])
    else:
        ws_dreams = wb.active
        ws_dreams.title = 'Dreams'
        ws_dreams.append(list(DREAM_IMPORT_HEADERS))
        for row in dream_rows:
            ws_dreams.append([
                row['entry_date'] or '',
                row['entry_time'] or '',
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
                '',
            ])

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    has_filters = (
        from_date is not None
        or to_date is not None
        or not include_daily
        or not include_dreams
    )
    filename = f'aidiary_export_{stamp}.zip'
    if has_filters:
        filename = f'aidiary_export_filtered_{stamp}.zip'

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

    manifest_assets: dict[str, dict[str, object]] = {}
    if include_daily:
        for row_index, row in enumerate(daily_rows, start=2):
            storage_key = row['image_storage_key']
            entry_attachments = daily_attachment_rows.get(int(row['id']), [])
            if not storage_key and not entry_attachments:
                continue
            image_bytes = read_media_bytes(storage_key)
            if storage_key and not image_bytes:
                continue
            asset_ref = _build_entry_asset_ref('daily', row)
            ws_daily.cell(row=row_index, column=len(DAILY_IMPORT_HEADERS)).value = asset_ref
            image_filename = _image_filename_for_storage_key(storage_key)
            manifest_assets[asset_ref] = {
                'entry_type': 'daily',
                'image_filename': image_filename,
                'image_source': row['image_source'],
                'image_position_x': row['image_position_x'],
                'image_position_y': row['image_position_y'],
                'image_prompt': row['image_prompt'],
                'recycled_image_prompt': row['recycled_image_prompt'],
                'attachments': [
                    {
                        'package_filename': _package_attachment_filename(attachment, index),
                        'original_filename': attachment['original_filename'],
                        'mime_type': attachment['mime_type'],
                        'asset_role': attachment['asset_role'],
                        'file_size_bytes': int(attachment['file_size_bytes'] or 0),
                        'sort_order': int(attachment['sort_order'] or 0),
                    }
                    for index, attachment in enumerate(entry_attachments, start=1)
                    if attachment['storage_key'] and read_media_bytes(attachment['storage_key'])
                ],
            }

    if include_dreams:
        ws_target = wb['Dreams']
        for row_index, row in enumerate(dream_rows, start=2):
            storage_key = row['image_storage_key']
            entry_attachments = dream_attachment_rows.get(int(row['id']), [])
            if not storage_key and not entry_attachments:
                continue
            image_bytes = read_media_bytes(storage_key)
            if storage_key and not image_bytes:
                continue
            asset_ref = _build_entry_asset_ref('dream', row)
            ws_target.cell(row=row_index, column=len(DREAM_IMPORT_HEADERS)).value = asset_ref
            image_filename = _image_filename_for_storage_key(storage_key)
            manifest_assets[asset_ref] = {
                'entry_type': 'dream',
                'image_filename': image_filename,
                'image_source': row['image_source'],
                'image_position_x': row['image_position_x'],
                'image_position_y': row['image_position_y'],
                'image_prompt': row['image_prompt'],
                'recycled_image_prompt': row['recycled_image_prompt'],
                'attachments': [
                    {
                        'package_filename': _package_attachment_filename(attachment, index),
                        'original_filename': attachment['original_filename'],
                        'mime_type': attachment['mime_type'],
                        'asset_role': attachment['asset_role'],
                        'file_size_bytes': int(attachment['file_size_bytes'] or 0),
                        'sort_order': int(attachment['sort_order'] or 0),
                    }
                    for index, attachment in enumerate(entry_attachments, start=1)
                    if attachment['storage_key'] and read_media_bytes(attachment['storage_key'])
                ],
            }

    final_workbook_buffer = io.BytesIO()
    wb.save(final_workbook_buffer)
    final_workbook_buffer.seek(0)

    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as package_zip:
        package_zip.writestr('entries.xlsx', final_workbook_buffer.getvalue())
        for asset_ref, asset_meta in manifest_assets.items():
            image_filename = asset_meta['image_filename']
            source_rows = daily_rows if asset_meta['entry_type'] == 'daily' else dream_rows
            source_row = next(
                (
                    row
                    for row in source_rows
                    if _build_entry_asset_ref(asset_meta['entry_type'], row) == asset_ref
                ),
                None,
            )
            if source_row is None:
                continue

            if image_filename:
                image_bytes = read_media_bytes(source_row['image_storage_key'])
                if image_bytes:
                    package_zip.writestr(f'media/{asset_ref}/{image_filename}', image_bytes)

            for attachment_meta in asset_meta.get('attachments', []):
                if not isinstance(attachment_meta, dict):
                    continue
                package_filename = str(attachment_meta.get('package_filename') or '').strip()
                if not package_filename:
                    continue
                attachment_rows = (
                    daily_attachment_rows.get(int(source_row['id']), [])
                    if asset_meta['entry_type'] == 'daily'
                    else dream_attachment_rows.get(int(source_row['id']), [])
                )
                attachment_storage_key = next(
                    (
                        attachment_row['storage_key']
                        for index, attachment_row in enumerate(attachment_rows, start=1)
                        if _package_attachment_filename(attachment_row, index) == package_filename
                    ),
                    None,
                )
                attachment_bytes = read_media_bytes(attachment_storage_key)
                if not attachment_bytes:
                    continue
                package_zip.writestr(
                    f'media/{asset_ref}/{package_filename}',
                    attachment_bytes,
                )

        package_zip.writestr(
            'manifest.json',
            json.dumps(
                {
                    'package_type': 'aidiary_export',
                    'version': 1,
                    'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'assets': manifest_assets,
                },
                ensure_ascii=True,
                indent=2,
            ),
        )

    package_buffer.seek(0)

    response = send_file(
        package_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=filename,
    )
    response.headers['Access-Control-Expose-Headers'] = 'X-AiDiary-Export-Token'
    if export_record['guard_token']:
        response.headers['X-AiDiary-Export-Token'] = export_record['guard_token']
    return response

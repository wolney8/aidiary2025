from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from services.ai_config import DEFAULT_ANALYSIS_MODEL
from services.database import connect_sqlite
from services.openai_svc import AnalysisRateLimitError, OpenAIService

cbt_bp = Blueprint('cbt', __name__)

WORKSHEET_TYPE = 'thought_record'
ALLOWED_STATUSES = {'draft', 'completed'}
ALLOWED_ENTRY_TYPES = {'daily', 'dream'}
ENTRY_TABLES = {
    'daily': 'dailydiary_entries',
    'dream': 'dreamdiary_entries',
}
MAX_TITLE_LENGTH = 100
MAX_FIELD_LENGTH = 6000
MAX_FEELINGS = 8
MAX_FEELING_LABEL_LENGTH = 40

DATA_FIELDS = (
    'situation',
    'unhelpful_thoughts',
    'evidence_for',
    'evidence_against',
    'balanced_thought',
    'next_step',
)


def get_db() -> sqlite3.Connection:
    return connect_sqlite(
        current_app,
        log_label='CBT',
        timeout=10,
        foreign_keys=True,
    )


def _coerce_text(value: object, field_name: str, *, max_length: int) -> str:
    text = str(value or '').strip()
    if len(text) > max_length:
        raise ValueError(f'{field_name} must be {max_length} characters or fewer')
    return text


def _coerce_step(value: object) -> int:
    try:
        step = int(value or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError('Current step must be between 1 and 7') from exc
    if step < 1 or step > 7:
        raise ValueError('Current step must be between 1 and 7')
    return step


def _coerce_record_date(value: object) -> str:
    record_date = str(value or '').strip()
    try:
        return date.fromisoformat(record_date).isoformat()
    except (TypeError, ValueError) as exc:
        raise ValueError('Thought record date must be a valid date') from exc


def _coerce_feelings(value: object, field_name: str) -> list[dict[str, object]]:
    if value in (None, ''):
        return []
    if not isinstance(value, list):
        raise ValueError(f'{field_name} must be a list')
    if len(value) > MAX_FEELINGS:
        raise ValueError(f'{field_name} can contain at most {MAX_FEELINGS} feelings')

    feelings: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f'{field_name} contains an invalid feeling')
        label = _coerce_text(
            item.get('label'),
            'Feeling label',
            max_length=MAX_FEELING_LABEL_LENGTH,
        )
        intensity = item.get('intensity')
        if not label:
            raise ValueError('Feeling label is required')
        if isinstance(intensity, bool):
            raise ValueError('Feeling intensity must be between 0 and 100')
        try:
            rating = int(intensity)
        except (TypeError, ValueError) as exc:
            raise ValueError('Feeling intensity must be between 0 and 100') from exc
        if rating < 0 or rating > 100:
            raise ValueError('Feeling intensity must be between 0 and 100')
        feelings.append({'label': label, 'intensity': rating})
    return feelings


def _decode_feelings(value: object) -> list[dict[str, object]]:
    try:
        decoded = json.loads(str(value or '[]'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []


def _validate_link(
    conn: sqlite3.Connection,
    user_id: int,
    entry_type: object,
    entry_id: object,
) -> tuple[str | None, int | None, str | None]:
    if entry_type in (None, '') and entry_id in (None, ''):
        return None, None, None

    normalised_type = str(entry_type or '').strip().lower()
    if normalised_type not in ALLOWED_ENTRY_TYPES:
        raise ValueError('Linked entry type must be daily or dream')
    try:
        normalised_id = int(entry_id)
    except (TypeError, ValueError) as exc:
        raise ValueError('Linked entry is invalid') from exc
    if normalised_id < 1:
        raise ValueError('Linked entry is invalid')

    table_name = ENTRY_TABLES[normalised_type]
    try:
        owned_entry = conn.execute(
            f'SELECT entry_date FROM {table_name} WHERE id = ? AND user_id = ?',
            (normalised_id, user_id),
        ).fetchone()
    except sqlite3.OperationalError:
        owned_entry = None
    if not owned_entry:
        raise ValueError('Linked entry was not found')
    return normalised_type, normalised_id, owned_entry['entry_date']


def _worksheet_query(where_clause: str) -> str:
    return f'''
        SELECT w.id, w.user_id, w.worksheet_type, w.title, w.status,
               w.current_step, w.record_date, w.linked_entry_type, w.linked_entry_id,
               w.created_at, w.updated_at, w.completed_at,
               d.situation, d.feelings_before_json, d.unhelpful_thoughts,
               d.evidence_for, d.evidence_against, d.balanced_thought,
               d.feelings_after_json, d.next_step, d.ai_response,
               d.ai_responded_at, d.ai_response_outdated
        FROM cbt_worksheets w
        JOIN cbt_thought_record_data d ON d.worksheet_id = w.id
        WHERE {where_clause}
    '''


def _serialise_worksheet(row: sqlite3.Row) -> dict[str, Any]:
    feelings_before = _decode_feelings(row['feelings_before_json'])
    feelings_after = _decode_feelings(row['feelings_after_json'])
    before_peak = max(
        (int(item.get('intensity', 0)) for item in feelings_before),
        default=None,
    )
    after_peak = max(
        (int(item.get('intensity', 0)) for item in feelings_after),
        default=None,
    )
    return {
        'id': row['id'],
        'worksheet_type': row['worksheet_type'],
        'title': row['title'],
        'status': row['status'],
        'current_step': row['current_step'],
        'record_date': row['record_date'],
        'linked_entry_type': row['linked_entry_type'],
        'linked_entry_id': row['linked_entry_id'],
        'situation': row['situation'],
        'feelings_before': feelings_before,
        'unhelpful_thoughts': row['unhelpful_thoughts'],
        'evidence_for': row['evidence_for'],
        'evidence_against': row['evidence_against'],
        'balanced_thought': row['balanced_thought'],
        'feelings_after': feelings_after,
        'next_step': row['next_step'],
        'ai_response': row['ai_response'],
        'ai_responded_at': row['ai_responded_at'],
        'ai_response_outdated': bool(row['ai_response_outdated']),
        'before_peak_intensity': before_peak,
        'after_peak_intensity': after_peak,
        'intensity_change': (
            after_peak - before_peak
            if before_peak is not None and after_peak is not None
            else None
        ),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'completed_at': row['completed_at'],
    }


def _get_owned_worksheet(
    conn: sqlite3.Connection,
    worksheet_id: int,
    user_id: int,
) -> sqlite3.Row | None:
    return conn.execute(
        _worksheet_query('w.id = ? AND w.user_id = ?'),
        (worksheet_id, user_id),
    ).fetchone()


def _parse_data_payload(payload: dict[str, Any], existing: sqlite3.Row | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field_name in DATA_FIELDS:
        source_value = payload.get(field_name)
        if field_name not in payload and existing is not None:
            source_value = existing[field_name]
        data[field_name] = _coerce_text(
            source_value,
            field_name.replace('_', ' ').title(),
            max_length=MAX_FIELD_LENGTH,
        )

    before_value = payload.get('feelings_before')
    if 'feelings_before' not in payload and existing is not None:
        before_value = _decode_feelings(existing['feelings_before_json'])
    after_value = payload.get('feelings_after')
    if 'feelings_after' not in payload and existing is not None:
        after_value = _decode_feelings(existing['feelings_after_json'])
    data['feelings_before'] = _coerce_feelings(before_value, 'Feelings before')
    data['feelings_after'] = _coerce_feelings(after_value, 'Feelings after')
    return data


def _completion_error(data: dict[str, Any]) -> str | None:
    required_text = (
        'situation',
        'unhelpful_thoughts',
        'evidence_for',
        'evidence_against',
        'balanced_thought',
    )
    if any(not data[field] for field in required_text):
        return 'Complete all seven reflection steps before finishing'
    if not data['feelings_before'] or not data['feelings_after']:
        return 'Add at least one feeling before and after the reflection'
    return None


def _persist_worksheet_fields(
    conn: sqlite3.Connection,
    *,
    worksheet_id: int,
    user_id: int,
    title: str,
    current_step: int,
    record_date: str,
    data: dict[str, Any],
    mark_ai_response_outdated: bool,
) -> None:
    conn.execute(
        '''
        UPDATE cbt_worksheets
        SET title = ?, current_step = ?, record_date = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        ''',
        (title, current_step, record_date, worksheet_id, user_id),
    )
    conn.execute(
        '''
        UPDATE cbt_thought_record_data
        SET situation = ?, feelings_before_json = ?, unhelpful_thoughts = ?,
            evidence_for = ?, evidence_against = ?, balanced_thought = ?,
            feelings_after_json = ?, next_step = ?,
            ai_response_outdated = CASE
                WHEN ? = 1 AND ai_response <> '' THEN 1
                ELSE ai_response_outdated
            END
        WHERE worksheet_id = ?
        ''',
        (
            data['situation'],
            json.dumps(data['feelings_before']),
            data['unhelpful_thoughts'],
            data['evidence_for'],
            data['evidence_against'],
            data['balanced_thought'],
            json.dumps(data['feelings_after']),
            data['next_step'],
            int(mark_ai_response_outdated),
            worksheet_id,
        ),
    )


def _analysis_input_changed(
    existing: sqlite3.Row,
    *,
    title: str,
    record_date: str,
    data: dict[str, Any],
) -> bool:
    if title != str(existing['title'] or ''):
        return True
    if record_date != str(existing['record_date'] or ''):
        return True
    if any(data[field_name] != str(existing[field_name] or '') for field_name in DATA_FIELDS):
        return True
    return (
        data['feelings_before'] != _decode_feelings(existing['feelings_before_json'])
        or data['feelings_after'] != _decode_feelings(existing['feelings_after_json'])
    )


def _load_thought_record_analysis_options(
    conn: sqlite3.Connection,
    user_id: int,
) -> dict[str, object]:
    try:
        row = conn.execute(
            '''
            SELECT ai_tone, ai_verbosity, ai_focus, ai_model,
                   display_name, pronouns, gender, custom_guidance, sex, goals
            FROM users
            WHERE id = ?
            ''',
            (user_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None

    options: dict[str, object] = {
        'ai_style': 'reflective',
        'ai_tone': 'friendly',
        'ai_verbosity': 'balanced',
        'ai_focus': 'reflective',
        'ai_model': DEFAULT_ANALYSIS_MODEL,
        'personal_context': None,
    }
    if not row:
        return options

    for field_name in ('ai_tone', 'ai_verbosity', 'ai_focus', 'ai_model'):
        value = str(row[field_name] or '').strip()
        if value:
            options[field_name] = value

    personal_context = [
        ('Display name', row['display_name']),
        ('Pronouns', row['pronouns']),
        ('Gender', row['gender'] or row['sex']),
        ('Custom guidance', row['custom_guidance'] or row['goals']),
    ]
    context_lines = [
        f'{label}: {str(value).strip()}'
        for label, value in personal_context
        if str(value or '').strip()
    ]
    options['personal_context'] = '\n'.join(context_lines) or None
    return options


def _format_thought_record_for_analysis(row: sqlite3.Row) -> str:
    def bounded_text(value: object, limit: int = 1200) -> str:
        text = str(value or '').strip()
        return text if len(text) <= limit else text[:limit].rstrip() + '...'

    def format_feelings(raw: object) -> str:
        feelings = _decode_feelings(raw)
        return ', '.join(
            f"{str(item.get('label') or '').strip()} ({int(item.get('intensity') or 0)}%)"
            for item in feelings
            if str(item.get('label') or '').strip()
        ) or 'Not recorded'

    return '\n'.join([
        f"Title: {bounded_text(row['title'], 100) or 'Untitled thought record'}",
        f"Date: {row['record_date']}",
        f"Situation: {bounded_text(row['situation'])}",
        f"Initial feelings: {format_feelings(row['feelings_before_json'])}",
        f"Unhelpful thoughts: {bounded_text(row['unhelpful_thoughts'])}",
        f"Evidence for: {bounded_text(row['evidence_for'])}",
        f"Evidence against: {bounded_text(row['evidence_against'])}",
        f"Balanced perspective: {bounded_text(row['balanced_thought'])}",
        f"Feelings after: {format_feelings(row['feelings_after_json'])}",
        f"Next step: {bounded_text(row['next_step']) or 'Not recorded'}",
    ])


@cbt_bp.route('/cbt/worksheets', methods=['GET'])
@jwt_required()
def list_worksheets():
    user_id = int(get_jwt_identity())
    status = str(request.args.get('status') or '').strip().lower()
    linked_type = str(request.args.get('linked_entry_type') or '').strip().lower()
    linked_id = request.args.get('linked_entry_id')

    clauses = ['w.user_id = ?']
    params: list[object] = [user_id]
    if status:
        if status not in ALLOWED_STATUSES:
            return jsonify({'error': 'Status filter is invalid'}), 400
        clauses.append('w.status = ?')
        params.append(status)
    if linked_type or linked_id:
        if linked_type not in ALLOWED_ENTRY_TYPES:
            return jsonify({'error': 'Linked entry type must be daily or dream'}), 400
        try:
            linked_entry_id = int(linked_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'Linked entry is invalid'}), 400
        clauses.extend(['w.linked_entry_type = ?', 'w.linked_entry_id = ?'])
        params.extend([linked_type, linked_entry_id])

    conn = get_db()
    rows = conn.execute(
        _worksheet_query(' AND '.join(clauses)) +
        ' ORDER BY w.updated_at DESC, w.id DESC',
        params,
    ).fetchall()
    conn.close()
    return jsonify([_serialise_worksheet(row) for row in rows]), 200


@cbt_bp.route('/cbt/worksheets', methods=['POST'])
@jwt_required()
def create_worksheet():
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    conn = get_db()
    try:
        title = _coerce_text(payload.get('title'), 'Title', max_length=MAX_TITLE_LENGTH)
        current_step = _coerce_step(payload.get('current_step'))
        linked_type, linked_id, linked_entry_date = _validate_link(
            conn,
            user_id,
            payload.get('linked_entry_type'),
            payload.get('linked_entry_id'),
        )
        record_date = _coerce_record_date(
            payload.get('record_date') or linked_entry_date or date.today().isoformat()
        )
        data = _parse_data_payload(payload)
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 400

    cursor = conn.execute(
        '''
        INSERT INTO cbt_worksheets (
            user_id, worksheet_type, title, status, current_step,
            record_date, linked_entry_type, linked_entry_id
        ) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)
        ''',
        (
            user_id,
            WORKSHEET_TYPE,
            title,
            current_step,
            record_date,
            linked_type,
            linked_id,
        ),
    )
    worksheet_id = int(cursor.lastrowid)
    conn.execute(
        '''
        INSERT INTO cbt_thought_record_data (
            worksheet_id, situation, feelings_before_json, unhelpful_thoughts,
            evidence_for, evidence_against, balanced_thought,
            feelings_after_json, next_step
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            worksheet_id,
            data['situation'],
            json.dumps(data['feelings_before']),
            data['unhelpful_thoughts'],
            data['evidence_for'],
            data['evidence_against'],
            data['balanced_thought'],
            json.dumps(data['feelings_after']),
            data['next_step'],
        ),
    )
    conn.commit()
    row = _get_owned_worksheet(conn, worksheet_id, user_id)
    conn.close()
    return jsonify(_serialise_worksheet(row)), 201


@cbt_bp.route('/cbt/worksheets/<int:worksheet_id>', methods=['GET'])
@jwt_required()
def get_worksheet(worksheet_id: int):
    user_id = int(get_jwt_identity())
    conn = get_db()
    row = _get_owned_worksheet(conn, worksheet_id, user_id)
    conn.close()
    if not row:
        return jsonify({'error': 'Worksheet not found'}), 404
    return jsonify(_serialise_worksheet(row)), 200


@cbt_bp.route('/cbt/worksheets/<int:worksheet_id>', methods=['PUT'])
@jwt_required()
def update_worksheet(worksheet_id: int):
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    conn = get_db()
    existing = _get_owned_worksheet(conn, worksheet_id, user_id)
    if not existing:
        conn.close()
        return jsonify({'error': 'Worksheet not found'}), 404
    if existing['status'] == 'completed':
        conn.close()
        return jsonify({'error': 'Completed worksheets are read-only'}), 409

    try:
        title = _coerce_text(
            payload.get('title', existing['title']),
            'Title',
            max_length=MAX_TITLE_LENGTH,
        )
        current_step = _coerce_step(payload.get('current_step', existing['current_step']))
        record_date = _coerce_record_date(
            payload.get('record_date', existing['record_date'])
        )
        data = _parse_data_payload(payload, existing)
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 400

    _persist_worksheet_fields(
        conn,
        worksheet_id=worksheet_id,
        user_id=user_id,
        title=title,
        current_step=current_step,
        record_date=record_date,
        data=data,
        mark_ai_response_outdated=_analysis_input_changed(
            existing,
            title=title,
            record_date=record_date,
            data=data,
        ),
    )
    conn.commit()
    row = _get_owned_worksheet(conn, worksheet_id, user_id)
    conn.close()
    return jsonify(_serialise_worksheet(row)), 200


@cbt_bp.route('/cbt/worksheets/<int:worksheet_id>/revise', methods=['PUT'])
@jwt_required()
def revise_completed_worksheet(worksheet_id: int):
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    conn = get_db()
    existing = _get_owned_worksheet(conn, worksheet_id, user_id)
    if not existing:
        conn.close()
        return jsonify({'error': 'Worksheet not found'}), 404
    if existing['status'] != 'completed':
        conn.close()
        return jsonify({'error': 'Only completed worksheets can be revised'}), 409

    try:
        title = _coerce_text(
            payload.get('title', existing['title']),
            'Title',
            max_length=MAX_TITLE_LENGTH,
        )
        record_date = _coerce_record_date(
            payload.get('record_date', existing['record_date'])
        )
        data = _parse_data_payload(payload, existing)
        completion_error = _completion_error(data)
        if completion_error:
            raise ValueError(completion_error)
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 400

    _persist_worksheet_fields(
        conn,
        worksheet_id=worksheet_id,
        user_id=user_id,
        title=title,
        current_step=7,
        record_date=record_date,
        data=data,
        mark_ai_response_outdated=_analysis_input_changed(
            existing,
            title=title,
            record_date=record_date,
            data=data,
        ),
    )
    conn.commit()
    row = _get_owned_worksheet(conn, worksheet_id, user_id)
    conn.close()
    return jsonify(_serialise_worksheet(row)), 200


@cbt_bp.route('/cbt/worksheets/<int:worksheet_id>/complete', methods=['POST'])
@jwt_required()
def complete_worksheet(worksheet_id: int):
    user_id = int(get_jwt_identity())
    conn = get_db()
    existing = _get_owned_worksheet(conn, worksheet_id, user_id)
    if not existing:
        conn.close()
        return jsonify({'error': 'Worksheet not found'}), 404

    data = _parse_data_payload({}, existing)
    completion_error = _completion_error(data)
    if completion_error:
        conn.close()
        return jsonify({'error': completion_error}), 400

    conn.execute(
        '''
        UPDATE cbt_worksheets
        SET status = 'completed', current_step = 7,
            completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        ''',
        (worksheet_id, user_id),
    )
    conn.commit()
    row = _get_owned_worksheet(conn, worksheet_id, user_id)
    conn.close()
    return jsonify(_serialise_worksheet(row)), 200


@cbt_bp.route('/cbt/worksheets/<int:worksheet_id>/analyse', methods=['POST'])
@jwt_required()
def analyse_worksheet(worksheet_id: int):
    user_id = int(get_jwt_identity())
    conn = get_db()
    existing = _get_owned_worksheet(conn, worksheet_id, user_id)
    if not existing:
        conn.close()
        return jsonify({'error': 'Worksheet not found'}), 404
    analysis_source = ' '.join(
        str(existing[field_name] or '').strip()
        for field_name in DATA_FIELDS
    ).strip()
    if len(analysis_source) < 20:
        conn.close()
        return jsonify({
            'error': 'Add more detail to the thought record before requesting a response'
        }), 400

    analysis_options = _load_thought_record_analysis_options(conn, user_id)
    analysis_text = _format_thought_record_for_analysis(existing)
    conn.close()

    try:
        ai_response = OpenAIService().analyse_thought_record(
            analysis_text,
            analysis_options=analysis_options,
        )
    except AnalysisRateLimitError:
        return jsonify({
            'error': 'AI analysis is temporarily rate-limited. Please try again later.'
        }), 429
    except Exception:
        current_app.logger.exception(
            'Thought record AI analysis failed for worksheet %s', worksheet_id
        )
        return jsonify({'error': 'The AI response could not be generated'}), 502

    conn = get_db()
    current = _get_owned_worksheet(conn, worksheet_id, user_id)
    if not current:
        conn.close()
        return jsonify({'error': 'Worksheet is no longer available for analysis'}), 409
    conn.execute(
        '''
        UPDATE cbt_thought_record_data
        SET ai_response = ?, ai_responded_at = CURRENT_TIMESTAMP,
            ai_response_outdated = 0
        WHERE worksheet_id = ?
        ''',
        (ai_response, worksheet_id),
    )
    conn.execute(
        '''
        UPDATE cbt_worksheets
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        ''',
        (worksheet_id, user_id),
    )
    conn.commit()
    row = _get_owned_worksheet(conn, worksheet_id, user_id)
    conn.close()
    return jsonify(_serialise_worksheet(row)), 200


@cbt_bp.route('/cbt/worksheets/<int:worksheet_id>', methods=['DELETE'])
@jwt_required()
def delete_worksheet(worksheet_id: int):
    user_id = int(get_jwt_identity())
    conn = get_db()
    cursor = conn.execute(
        'DELETE FROM cbt_worksheets WHERE id = ? AND user_id = ?',
        (worksheet_id, user_id),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({'error': 'Worksheet not found'}), 404
    return jsonify({'message': 'Worksheet deleted'}), 200

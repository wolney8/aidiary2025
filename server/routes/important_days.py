from __future__ import annotations

from calendar import monthrange
from datetime import datetime
import sqlite3

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

important_days_bp = Blueprint('important_days', __name__)

ALLOWED_CATEGORIES = {'birthday', 'anniversary', 'milestone', 'other'}
ALLOWED_RECURRENCES = {'once', 'yearly'}
ALLOWED_ICONS = {
    'cake',
    'favorite',
    'flag',
    'event',
    'celebration',
    'star',
    'sentiment_neutral',
    'sentiment_dissatisfied',
    'mood_bad',
}
ALLOWED_ACCENT_COLORS = {'amber', 'rose', 'blue', 'violet', 'emerald', 'slate'}
MAX_LABEL_LENGTH = 60
MAX_NOTE_LENGTH = 160


def get_db():
    db_path = current_app.config['DATABASE_PATH']
    current_app.logger.debug('Important days get_db connecting to %s', db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _coerce_required_text(value: object, field_name: str, *, max_length: int) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    if len(text) > max_length:
        raise ValueError(f'{field_name} must be {max_length} characters or fewer')
    return text


def _coerce_optional_text(value: object, *, max_length: int) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    if len(text) > max_length:
        raise ValueError(f'Note must be {max_length} characters or fewer')
    return text


def _coerce_int(
    value: object,
    field_name: str,
    *,
    required: bool,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int | None:
    if value in (None, ''):
        if required:
            raise ValueError(f'{field_name} is required')
        return None

    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field_name} must be a valid number') from exc

    if min_value is not None and number < min_value:
        raise ValueError(f'{field_name} is out of range')
    if max_value is not None and number > max_value:
        raise ValueError(f'{field_name} is out of range')

    return number


def _coerce_category(value: object) -> str:
    category = str(value or 'other').strip().lower()
    if category not in ALLOWED_CATEGORIES:
        raise ValueError('Category is invalid')
    return category


def _coerce_recurrence(value: object) -> str:
    recurrence = str(value or 'yearly').strip().lower()
    if recurrence not in ALLOWED_RECURRENCES:
        raise ValueError('Recurrence is invalid')
    return recurrence


def _coerce_icon_name(value: object) -> str:
    icon_name = str(value or 'event').strip()
    if icon_name not in ALLOWED_ICONS:
        raise ValueError('Icon is invalid')
    return icon_name


def _coerce_accent_color(value: object) -> str:
    accent_color = str(value or 'amber').strip().lower()
    if accent_color not in ALLOWED_ACCENT_COLORS:
        raise ValueError('Accent colour is invalid')
    return accent_color


def _coerce_date(value: object) -> tuple[str, int, int, int]:
    text = str(value or '').strip()
    if not text:
        raise ValueError('Date is required')
    try:
        parsed = datetime.strptime(text, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('Date must use YYYY-MM-DD') from exc
    return text, parsed.month, parsed.day, parsed.year


def _validate_calendar_day(month: int, day: int, original_year: int | None) -> None:
    validation_year = original_year or 2024
    max_day = monthrange(validation_year, month)[1]
    if day > max_day:
        raise ValueError('Day is invalid for the selected month')


def _serialise_important_day(row: sqlite3.Row) -> dict[str, object]:
    starts_on = row['starts_on']
    if not starts_on:
        fallback_year = row['original_year'] or 2024
        starts_on = f"{fallback_year:04d}-{row['month']:02d}-{row['day']:02d}"

    return {
        'id': row['id'],
        'label': row['label'],
        'starts_on': starts_on,
        'month': row['month'],
        'day': row['day'],
        'original_year': row['original_year'],
        'category': row['category'],
        'recurrence': row['recurrence'] or 'yearly',
        'icon_name': row['icon_name'] or 'event',
        'accent_color': row['accent_color'] or 'amber',
        'note': row['note'] or '',
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def _parse_payload(
    payload: dict[str, object],
) -> tuple[str, str, int, int, int | None, str, str, str, str]:
    label = _coerce_required_text(payload.get('label'), 'Label', max_length=MAX_LABEL_LENGTH)
    starts_on, month, day, starts_on_year = _coerce_date(payload.get('starts_on'))
    original_year = _coerce_int(
        payload.get('original_year'),
        'Year',
        required=False,
        min_value=1900,
        max_value=2100,
    )
    if original_year is None:
        original_year = starts_on_year
    category = _coerce_category(payload.get('category'))
    recurrence = _coerce_recurrence(payload.get('recurrence'))
    icon_name = _coerce_icon_name(payload.get('icon_name'))
    accent_color = _coerce_accent_color(payload.get('accent_color'))
    note = _coerce_optional_text(payload.get('note'), max_length=MAX_NOTE_LENGTH)
    _validate_calendar_day(month, day, original_year)
    return (
        label,
        starts_on,
        month,
        day,
        original_year,
        category,
        recurrence,
        icon_name,
        accent_color,
        note,
    )


@important_days_bp.route('/important-days', methods=['GET'])
@jwt_required()
def list_important_days():
    user_id = int(get_jwt_identity())
    conn = get_db()
    rows = conn.execute(
        '''
        SELECT id, label, starts_on, month, day, original_year, category, recurrence,
               icon_name, accent_color, note, created_at, updated_at
        FROM important_days
        WHERE user_id = ?
        ORDER BY month ASC, day ASC, lower(label) ASC, id ASC
        ''',
        (user_id,),
    ).fetchall()
    conn.close()

    return jsonify([_serialise_important_day(row) for row in rows]), 200


@important_days_bp.route('/important-days', methods=['POST'])
@jwt_required()
def create_important_day():
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}

    try:
        (
            label,
            starts_on,
            month,
            day,
            original_year,
            category,
            recurrence,
            icon_name,
            accent_color,
            note,
        ) = _parse_payload(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO important_days (
            user_id, label, starts_on, month, day, original_year, category,
            recurrence, icon_name, accent_color, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            user_id,
            label,
            starts_on,
            month,
            day,
            original_year,
            category,
            recurrence,
            icon_name,
            accent_color,
            note,
        ),
    )
    conn.commit()
    row = conn.execute(
        '''
        SELECT id, label, starts_on, month, day, original_year, category, recurrence,
               icon_name, accent_color, note, created_at, updated_at
        FROM important_days
        WHERE id = ? AND user_id = ?
        ''',
        (cursor.lastrowid, user_id),
    ).fetchone()
    conn.close()

    return jsonify(_serialise_important_day(row)), 201


@important_days_bp.route('/important-days/<int:important_day_id>', methods=['PUT'])
@jwt_required()
def update_important_day(important_day_id: int):
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}

    try:
        (
            label,
            starts_on,
            month,
            day,
            original_year,
            category,
            recurrence,
            icon_name,
            accent_color,
            note,
        ) = _parse_payload(payload)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        '''
        UPDATE important_days
        SET label = ?, starts_on = ?, month = ?, day = ?, original_year = ?, category = ?,
            recurrence = ?, icon_name = ?, accent_color = ?, note = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        ''',
        (
            label,
            starts_on,
            month,
            day,
            original_year,
            category,
            recurrence,
            icon_name,
            accent_color,
            note,
            important_day_id,
            user_id,
        ),
    )
    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Important day not found'}), 404

    row = conn.execute(
        '''
        SELECT id, label, starts_on, month, day, original_year, category, recurrence,
               icon_name, accent_color, note, created_at, updated_at
        FROM important_days
        WHERE id = ? AND user_id = ?
        ''',
        (important_day_id, user_id),
    ).fetchone()
    conn.close()

    return jsonify(_serialise_important_day(row)), 200


@important_days_bp.route('/important-days/<int:important_day_id>', methods=['DELETE'])
@jwt_required()
def delete_important_day(important_day_id: int):
    user_id = int(get_jwt_identity())

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM important_days WHERE id = ? AND user_id = ?',
        (important_day_id, user_id),
    )
    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        return jsonify({'error': 'Important day not found'}), 404

    return jsonify({'message': 'Important day deleted', 'id': important_day_id}), 200

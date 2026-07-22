"""Privacy-safe anniversary resurfacing endpoints."""

from __future__ import annotations

from datetime import date
import re
import sqlite3

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.media_storage import resolve_image_url


on_this_day_bp = Blueprint('on_this_day', __name__)
ENTRY_TYPES = {'daily', 'dream', 'thought_record'}
MAX_RESULTS = 12
MAX_MONTH_RESULTS = 60
_WHITESPACE_PATTERN = re.compile(r'\s+')


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(current_app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    return conn


def _normalise_target_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Date must use YYYY-MM-DD format') from exc


def _normalise_target_month(value: str) -> date:
    if not re.fullmatch(r'\d{4}-\d{2}', value):
        raise ValueError('Month must use YYYY-MM format')
    try:
        return date.fromisoformat(f'{value}-01')
    except ValueError as exc:
        raise ValueError('Month must use YYYY-MM format') from exc


def _compact_text(value: object, limit: int = 220) -> str:
    text = _WHITESPACE_PATTERN.sub(' ', str(value or '')).strip()
    if len(text) <= limit:
        return text
    return f'{text[: limit - 1].rstrip()}…'


def _parse_tags(value: object) -> list[str]:
    return [tag.strip() for tag in str(value or '').split(',') if tag.strip()][:4]


def _resolved_image(row: sqlite3.Row) -> str | None:
    storage_key = row['image_storage_key']
    if storage_key:
        return resolve_image_url(storage_key)
    image_url = str(row['image_url'] or '').strip()
    if image_url and not image_url.startswith('data:image/'):
        return image_url
    return None


def _fetch_entry_rows(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    target: date,
) -> list[dict]:
    month_day = target.strftime('%m-%d')
    target_year = target.year
    entries: list[dict] = []

    daily_rows = conn.execute(
        """
        SELECT entry.id, entry.entry_date, entry.title, entry.user_message AS preview,
               entry.tags, entry.image_url, entry.image_storage_key, entry.image_source,
               (SELECT COUNT(*) FROM entry_assets asset
                WHERE asset.user_id = entry.user_id
                  AND asset.entry_type = 'daily' AND asset.entry_id = entry.id) AS attachment_count
        FROM dailydiary_entries entry
        WHERE entry.user_id = ?
          AND substr(entry.entry_date, 6, 5) = ?
          AND CAST(substr(entry.entry_date, 1, 4) AS INTEGER) < ?
          AND NOT EXISTS (
              SELECT 1 FROM entry_resurfacing_preferences hidden
              WHERE hidden.user_id = entry.user_id
                AND hidden.entry_type = 'daily' AND hidden.entry_id = entry.id
          )
        ORDER BY entry.entry_date DESC, entry.id DESC
        LIMIT ?
        """,
        (user_id, month_day, target_year, MAX_RESULTS),
    ).fetchall()
    for row in daily_rows:
        entries.append({
            'id': row['id'],
            'type': 'daily',
            'entry_date': row['entry_date'],
            'title': _compact_text(row['title']) or 'Daily entry',
            'preview': _compact_text(row['preview']),
            'tags': _parse_tags(row['tags']),
            'image_url': _resolved_image(row),
            'image_source': row['image_source'],
            'attachment_count': int(row['attachment_count'] or 0),
        })

    dream_rows = conn.execute(
        """
        SELECT entry.id, entry.entry_date, entry.title, entry.plot AS preview,
               entry.tags, entry.image_url, entry.image_storage_key, entry.image_source,
               (SELECT COUNT(*) FROM entry_assets asset
                WHERE asset.user_id = entry.user_id
                  AND asset.entry_type = 'dream' AND asset.entry_id = entry.id) AS attachment_count
        FROM dreamdiary_entries entry
        WHERE entry.user_id = ?
          AND substr(entry.entry_date, 6, 5) = ?
          AND CAST(substr(entry.entry_date, 1, 4) AS INTEGER) < ?
          AND NOT EXISTS (
              SELECT 1 FROM entry_resurfacing_preferences hidden
              WHERE hidden.user_id = entry.user_id
                AND hidden.entry_type = 'dream' AND hidden.entry_id = entry.id
          )
        ORDER BY entry.entry_date DESC, entry.id DESC
        LIMIT ?
        """,
        (user_id, month_day, target_year, MAX_RESULTS),
    ).fetchall()
    for row in dream_rows:
        entries.append({
            'id': row['id'],
            'type': 'dream',
            'entry_date': row['entry_date'],
            'title': _compact_text(row['title']) or 'Dream entry',
            'preview': _compact_text(row['preview']),
            'tags': _parse_tags(row['tags']),
            'image_url': _resolved_image(row),
            'image_source': row['image_source'],
            'attachment_count': int(row['attachment_count'] or 0),
        })

    thought_rows = conn.execute(
        """
        SELECT worksheet.id, worksheet.record_date AS entry_date, worksheet.title,
               data.situation, data.balanced_thought
        FROM cbt_worksheets worksheet
        JOIN cbt_thought_record_data data ON data.worksheet_id = worksheet.id
        WHERE worksheet.user_id = ? AND worksheet.status = 'completed'
          AND substr(worksheet.record_date, 6, 5) = ?
          AND CAST(substr(worksheet.record_date, 1, 4) AS INTEGER) < ?
          AND NOT EXISTS (
              SELECT 1 FROM entry_resurfacing_preferences hidden
              WHERE hidden.user_id = worksheet.user_id
                AND hidden.entry_type = 'thought_record'
                AND hidden.entry_id = worksheet.id
          )
        ORDER BY worksheet.record_date DESC, worksheet.id DESC
        LIMIT ?
        """,
        (user_id, month_day, target_year, MAX_RESULTS),
    ).fetchall()
    for row in thought_rows:
        preview = row['balanced_thought'] or row['situation']
        entries.append({
            'id': row['id'],
            'type': 'thought_record',
            'entry_date': row['entry_date'],
            'title': _compact_text(row['title']) or 'Thought record',
            'preview': _compact_text(preview),
            'tags': [],
            'image_url': None,
            'image_source': None,
            'attachment_count': 0,
        })

    entries.sort(key=lambda item: (item['entry_date'], item['type'], item['id']), reverse=True)
    return entries[:MAX_RESULTS]


def _fetch_month_entry_rows(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    target: date,
) -> list[dict]:
    month = target.strftime('%m')
    target_year = target.year
    entries: list[dict] = []

    queries = (
        (
            'daily',
            """
            SELECT entry.id, entry.entry_date, entry.title,
                   entry.user_message AS preview, entry.tags,
                   entry.image_url, entry.image_storage_key, entry.image_source,
                   (SELECT COUNT(*) FROM entry_assets asset
                    WHERE asset.user_id = entry.user_id
                      AND asset.entry_type = 'daily' AND asset.entry_id = entry.id) AS attachment_count
            FROM dailydiary_entries entry
            WHERE entry.user_id = ? AND substr(entry.entry_date, 6, 2) = ?
              AND CAST(substr(entry.entry_date, 1, 4) AS INTEGER) < ?
              AND NOT EXISTS (
                  SELECT 1 FROM entry_resurfacing_preferences hidden
                  WHERE hidden.user_id = entry.user_id
                    AND hidden.entry_type = 'daily' AND hidden.entry_id = entry.id
              )
            ORDER BY entry.entry_date DESC, entry.id DESC
            LIMIT ?
            """,
            'Daily entry',
        ),
        (
            'dream',
            """
            SELECT entry.id, entry.entry_date, entry.title,
                   entry.plot AS preview, entry.tags,
                   entry.image_url, entry.image_storage_key, entry.image_source,
                   (SELECT COUNT(*) FROM entry_assets asset
                    WHERE asset.user_id = entry.user_id
                      AND asset.entry_type = 'dream' AND asset.entry_id = entry.id) AS attachment_count
            FROM dreamdiary_entries entry
            WHERE entry.user_id = ? AND substr(entry.entry_date, 6, 2) = ?
              AND CAST(substr(entry.entry_date, 1, 4) AS INTEGER) < ?
              AND NOT EXISTS (
                  SELECT 1 FROM entry_resurfacing_preferences hidden
                  WHERE hidden.user_id = entry.user_id
                    AND hidden.entry_type = 'dream' AND hidden.entry_id = entry.id
              )
            ORDER BY entry.entry_date DESC, entry.id DESC
            LIMIT ?
            """,
            'Dream entry',
        ),
    )
    for entry_type, query, fallback_title in queries:
        rows = conn.execute(
            query,
            (user_id, month, target_year, MAX_MONTH_RESULTS),
        ).fetchall()
        for row in rows:
            entries.append({
                'id': row['id'],
                'type': entry_type,
                'entry_date': row['entry_date'],
                'title': _compact_text(row['title']) or fallback_title,
                'preview': _compact_text(row['preview']),
                'tags': _parse_tags(row['tags']),
                'image_url': _resolved_image(row),
                'image_source': row['image_source'],
                'attachment_count': int(row['attachment_count'] or 0),
            })

    thought_rows = conn.execute(
        """
        SELECT worksheet.id, worksheet.record_date AS entry_date, worksheet.title,
               data.situation, data.balanced_thought
        FROM cbt_worksheets worksheet
        JOIN cbt_thought_record_data data ON data.worksheet_id = worksheet.id
        WHERE worksheet.user_id = ? AND worksheet.status = 'completed'
          AND substr(worksheet.record_date, 6, 2) = ?
          AND CAST(substr(worksheet.record_date, 1, 4) AS INTEGER) < ?
          AND NOT EXISTS (
              SELECT 1 FROM entry_resurfacing_preferences hidden
              WHERE hidden.user_id = worksheet.user_id
                AND hidden.entry_type = 'thought_record'
                AND hidden.entry_id = worksheet.id
          )
        ORDER BY worksheet.record_date DESC, worksheet.id DESC
        LIMIT ?
        """,
        (user_id, month, target_year, MAX_MONTH_RESULTS),
    ).fetchall()
    for row in thought_rows:
        entries.append({
            'id': row['id'],
            'type': 'thought_record',
            'entry_date': row['entry_date'],
            'title': _compact_text(row['title']) or 'Thought record',
            'preview': _compact_text(row['balanced_thought'] or row['situation']),
            'tags': [],
            'image_url': None,
            'image_source': None,
            'attachment_count': 0,
        })

    entries.sort(key=lambda item: (item['entry_date'], item['type'], item['id']), reverse=True)
    return entries[:MAX_MONTH_RESULTS]


@on_this_day_bp.route('/on-this-day', methods=['GET'])
@jwt_required()
def get_on_this_day():
    user_id = int(get_jwt_identity())
    try:
        month_value = request.args.get('month')
        target = (
            _normalise_target_month(month_value)
            if month_value
            else _normalise_target_date(request.args.get('date'))
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    conn = get_db()
    try:
        setting = conn.execute(
            'SELECT show_on_this_day FROM users WHERE id = ?',
            (user_id,),
        ).fetchone()
        enabled = bool(setting and setting['show_on_this_day'])
        if not enabled:
            entries = []
        elif month_value:
            entries = _fetch_month_entry_rows(conn, user_id=user_id, target=target)
        else:
            entries = _fetch_entry_rows(conn, user_id=user_id, target=target)
    finally:
        conn.close()

    return jsonify({
        'enabled': enabled,
        'date': target.isoformat(),
        'entries': entries,
    }), 200


@on_this_day_bp.route('/on-this-day/hide', methods=['POST'])
@jwt_required()
def hide_on_this_day_entry():
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    entry_type = str(payload.get('entry_type') or '').strip()
    try:
        entry_id = int(payload.get('entry_id'))
    except (TypeError, ValueError):
        entry_id = 0
    if entry_type not in ENTRY_TYPES or entry_id <= 0:
        return jsonify({'error': 'Choose a valid entry to hide'}), 400

    ownership_queries = {
        'daily': 'SELECT 1 FROM dailydiary_entries WHERE id = ? AND user_id = ?',
        'dream': 'SELECT 1 FROM dreamdiary_entries WHERE id = ? AND user_id = ?',
        'thought_record': 'SELECT 1 FROM cbt_worksheets WHERE id = ? AND user_id = ?',
    }
    conn = get_db()
    try:
        owned = conn.execute(ownership_queries[entry_type], (entry_id, user_id)).fetchone()
        if not owned:
            return jsonify({'error': 'Entry not found'}), 404
        conn.execute(
            """
            INSERT OR IGNORE INTO entry_resurfacing_preferences
                (user_id, entry_type, entry_id)
            VALUES (?, ?, ?)
            """,
            (user_id, entry_type, entry_id),
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({'message': 'Memory hidden', 'entry_type': entry_type, 'entry_id': entry_id}), 200

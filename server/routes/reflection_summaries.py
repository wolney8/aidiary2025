from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from services.ai_config import DEFAULT_ANALYSIS_MODEL
from services.database import connect_sqlite, table_columns
from services.openai_svc import AnalysisRateLimitError, OpenAIService

reflection_summaries_bp = Blueprint('reflection_summaries', __name__)

PERIOD_TYPES = {'weekly', 'monthly'}
MAX_SOURCE_CHARS = 18000


def get_db() -> sqlite3.Connection:
    return connect_sqlite(
        current_app,
        log_label='Reflection summaries',
        timeout=10,
        foreign_keys=True,
    )


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return table_columns(conn, table_name)


def _expr(columns: set[str], column: str, alias: str | None = None) -> str:
    output = alias or column
    if column not in columns:
        return f"'' AS {output}"
    return f'{column} AS {output}' if output != column else column


def _parse_period(period_type_raw: object, period_start_raw: object) -> tuple[str, date, date]:
    period_type = str(period_type_raw or '').strip().lower()
    if period_type not in PERIOD_TYPES:
        raise ValueError('period_type must be weekly or monthly')
    try:
        period_start = date.fromisoformat(str(period_start_raw or '').strip())
    except (TypeError, ValueError) as exc:
        raise ValueError('period_start must be YYYY-MM-DD') from exc

    if period_type == 'weekly':
        period_start = period_start - timedelta(days=period_start.weekday())
        return period_type, period_start, period_start + timedelta(days=6)

    period_start = period_start.replace(day=1)
    next_month = (
        period_start.replace(year=period_start.year + 1, month=1, day=1)
        if period_start.month == 12
        else period_start.replace(month=period_start.month + 1, day=1)
    )
    return period_type, period_start, next_month - timedelta(days=1)


def _period_label(period_type: str, period_start: date, period_end: date) -> str:
    if period_type == 'weekly':
        return f"week of {period_start.strftime('%-d %B %Y')} to {period_end.strftime('%-d %B %Y')}"
    return period_start.strftime('%B %Y')


def _serialise_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        'id': row['id'],
        'period_type': row['period_type'],
        'period_start': row['period_start'],
        'period_end': row['period_end'],
        'title': row['title'],
        'summary_text': row['summary_text'],
        'themes': json.loads(row['themes_json'] or '[]'),
        'source_refs': json.loads(row['source_refs_json'] or '[]'),
        'model': row['model'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def _bounded(value: object, limit: int = 900) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[:limit].rstrip() + '...'


def _human_date(value: str) -> str:
    try:
        return date.fromisoformat(value).strftime('%A, %-d %B %Y')
    except ValueError:
        return value


def _load_user_analysis_options(conn: sqlite3.Connection, user_id: int) -> dict[str, object]:
    options: dict[str, object] = {
        'ai_style': 'reflective',
        'ai_tone': 'friendly',
        'ai_verbosity': 'balanced',
        'ai_focus': 'reflective',
        'ai_model': DEFAULT_ANALYSIS_MODEL,
        'personal_context': None,
    }
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
        return options
    if not row:
        return options

    for field_name in ('ai_tone', 'ai_verbosity', 'ai_focus', 'ai_model'):
        value = str(row[field_name] or '').strip()
        if value:
            options[field_name] = value

    personal_lines = [
        f'{label}: {str(value).strip()}'
        for label, value in (
            ('Display name', row['display_name']),
            ('Pronouns', row['pronouns']),
            ('Gender', row['gender'] or row['sex']),
            ('Custom guidance', row['custom_guidance'] or row['goals']),
        )
        if str(value or '').strip()
    ]
    options['personal_context'] = '\n'.join(personal_lines) or None
    return options


def _load_period_sources(
    conn: sqlite3.Connection,
    user_id: int,
    period_start: date,
    period_end: date,
) -> tuple[str, list[dict[str, object]]]:
    source_lines: list[str] = []
    refs: list[dict[str, object]] = []
    start_iso = period_start.isoformat()
    end_iso = period_end.isoformat()

    daily_columns = _table_columns(conn, 'dailydiary_entries')
    if daily_columns:
        if 'user_message' in daily_columns:
            body_expr = 'user_message AS body'
        elif 'entry' in daily_columns:
            body_expr = 'entry AS body'
        else:
            body_expr = "'' AS body"
        rows = conn.execute(
            f'''
            SELECT id, entry_date, {_expr(daily_columns, 'title')}, {body_expr},
                   {_expr(daily_columns, 'mood')}, {_expr(daily_columns, 'tags')},
                   {_expr(daily_columns, 'daily_people_names', 'people_names')},
                   {_expr(daily_columns, 'daily_places', 'places')},
                   {_expr(daily_columns, 'ai_response')}
            FROM dailydiary_entries
            WHERE user_id = ? AND date(entry_date) BETWEEN ? AND ?
            ORDER BY date(entry_date), id
            ''',
            (user_id, start_iso, end_iso),
        ).fetchall()
        for row in rows:
            refs.append({'type': 'daily', 'id': row['id'], 'date': row['entry_date'], 'theme': row['title'] or 'Daily entry'})
            source_lines.append(
                '\n'.join([
                    f"Daily entry on {_human_date(row['entry_date'])}: {row['title'] or 'Untitled'}",
                    f"Mood: {row['mood'] or 'Not recorded'}",
                    f"Tags: {row['tags'] or 'None'}",
                    f"People/places: {row['people_names'] or 'None'} / {row['places'] or 'None'}",
                    f"Entry: {_bounded(row['body'])}",
                    f"AI response: {_bounded(row['ai_response'], 500)}",
                ])
            )

    dream_columns = _table_columns(conn, 'dreamdiary_entries')
    if dream_columns:
        if 'plot' in dream_columns:
            body_expr = 'plot AS body'
        elif 'dream' in dream_columns:
            body_expr = 'dream AS body'
        else:
            body_expr = "'' AS body"
        rows = conn.execute(
            f'''
            SELECT id, entry_date, {_expr(dream_columns, 'title')}, {body_expr},
                   {_expr(dream_columns, 'mood')}, {_expr(dream_columns, 'tags')},
                   {_expr(dream_columns, 'dream_people_names', 'people_names')},
                   {_expr(dream_columns, 'dream_places', 'places')},
                   {_expr(dream_columns, 'summary')}, {_expr(dream_columns, 'interpretation')}
            FROM dreamdiary_entries
            WHERE user_id = ? AND date(entry_date) BETWEEN ? AND ?
            ORDER BY date(entry_date), id
            ''',
            (user_id, start_iso, end_iso),
        ).fetchall()
        for row in rows:
            refs.append({'type': 'dream', 'id': row['id'], 'date': row['entry_date'], 'theme': row['title'] or 'Dream entry'})
            source_lines.append(
                '\n'.join([
                    f"Dream entry on {_human_date(row['entry_date'])}: {row['title'] or 'Untitled'}",
                    f"Mood: {row['mood'] or 'Not recorded'}",
                    f"Tags: {row['tags'] or 'None'}",
                    f"People/places: {row['people_names'] or 'None'} / {row['places'] or 'None'}",
                    f"Plot: {_bounded(row['body'])}",
                    f"Summary/interpretation: {_bounded(' '.join([str(row['summary'] or ''), str(row['interpretation'] or '')]), 700)}",
                ])
            )

    try:
        rows = conn.execute(
            '''
            SELECT w.id, w.title, w.record_date, d.situation, d.balanced_thought,
                   d.next_step, d.ai_response
            FROM cbt_worksheets w
            JOIN cbt_thought_record_data d ON d.worksheet_id = w.id
            WHERE w.user_id = ? AND date(w.record_date) BETWEEN ? AND ?
            ORDER BY date(w.record_date), w.id
            ''',
            (user_id, start_iso, end_iso),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        refs.append({'type': 'thought_record', 'id': row['id'], 'date': row['record_date'], 'theme': row['title'] or 'Thought record'})
        source_lines.append(
            '\n'.join([
                f"Thought record on {_human_date(row['record_date'])}: {row['title'] or 'Untitled'}",
                f"Situation: {_bounded(row['situation'], 500)}",
                f"Balanced thought: {_bounded(row['balanced_thought'], 500)}",
                f"Next step: {_bounded(row['next_step'], 300)}",
                f"AI response: {_bounded(row['ai_response'], 400)}",
            ])
        )

    source_context = '\n\n---\n\n'.join(source_lines)
    return source_context[:MAX_SOURCE_CHARS], refs


@reflection_summaries_bp.route('/reflection-summaries', methods=['GET'])
@jwt_required()
def list_reflection_summaries():
    user_id = int(get_jwt_identity())
    period_type = str(request.args.get('period_type') or '').strip().lower()
    params: list[object] = [user_id]
    where = ['user_id = ?']
    if period_type:
        if period_type not in PERIOD_TYPES:
            return jsonify({'error': 'period_type must be weekly or monthly'}), 400
        where.append('period_type = ?')
        params.append(period_type)

    conn = get_db()
    rows = conn.execute(
        f'''
        SELECT id, period_type, period_start, period_end, title, summary_text,
               themes_json, source_refs_json, model, created_at, updated_at
        FROM reflection_summaries
        WHERE {' AND '.join(where)}
        ORDER BY period_start DESC, updated_at DESC
        LIMIT 36
        ''',
        params,
    ).fetchall()
    conn.close()
    return jsonify([_serialise_summary(row) for row in rows]), 200


@reflection_summaries_bp.route('/reflection-summaries/generate', methods=['POST'])
@jwt_required()
def generate_reflection_summary():
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    try:
        period_type, period_start, period_end = _parse_period(
            payload.get('period_type'),
            payload.get('period_start'),
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    conn = get_db()
    try:
        source_context, source_refs = _load_period_sources(conn, user_id, period_start, period_end)
        analysis_options = _load_user_analysis_options(conn, user_id)
        period_label = _period_label(period_type, period_start, period_end)

        if not source_refs:
            generated = {
                'title': f'No entries for {period_label}',
                'summary_text': 'There are no diary entries, dreams, or thought records in this period yet, so there is nothing reliable to summarise.',
                'themes': [],
            }
        else:
            generated = OpenAIService().generate_reflection_summary(
                period_type,
                period_label,
                source_context,
                analysis_options=analysis_options,
            )

        model = str(analysis_options.get('ai_model') or DEFAULT_ANALYSIS_MODEL)
        conn.execute(
            '''
            INSERT INTO reflection_summaries (
                user_id, period_type, period_start, period_end, title, summary_text,
                themes_json, source_refs_json, model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, period_type, period_start)
            DO UPDATE SET
                period_end = excluded.period_end,
                title = excluded.title,
                summary_text = excluded.summary_text,
                themes_json = excluded.themes_json,
                source_refs_json = excluded.source_refs_json,
                model = excluded.model,
                updated_at = CURRENT_TIMESTAMP
            ''',
            (
                user_id,
                period_type,
                period_start.isoformat(),
                period_end.isoformat(),
                str(generated['title']).strip(),
                str(generated['summary_text']).strip(),
                json.dumps(generated.get('themes') or []),
                json.dumps(source_refs),
                model,
            ),
        )
        conn.commit()
        row = conn.execute(
            '''
            SELECT id, period_type, period_start, period_end, title, summary_text,
                   themes_json, source_refs_json, model, created_at, updated_at
            FROM reflection_summaries
            WHERE user_id = ? AND period_type = ? AND period_start = ?
            ''',
            (user_id, period_type, period_start.isoformat()),
        ).fetchone()
    except AnalysisRateLimitError:
        conn.close()
        return jsonify({'error': 'AI summary generation is temporarily rate-limited. Please try again later.'}), 429
    except Exception:
        current_app.logger.exception('Reflection summary generation failed')
        conn.close()
        return jsonify({'error': 'Reflection summary could not be generated.'}), 502
    conn.close()
    return jsonify(_serialise_summary(row)), 200


@reflection_summaries_bp.route('/reflection-summaries/<int:summary_id>', methods=['DELETE'])
@jwt_required()
def delete_reflection_summary(summary_id: int):
    user_id = int(get_jwt_identity())
    conn = get_db()
    cursor = conn.execute(
        'DELETE FROM reflection_summaries WHERE id = ? AND user_id = ?',
        (summary_id, user_id),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        return jsonify({'error': 'Reflection summary not found'}), 404
    return jsonify({'message': 'Reflection summary deleted'}), 200

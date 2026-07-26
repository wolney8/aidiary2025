"""Authenticated SSE chat routes backed by durable SQLite history."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from time import perf_counter
from uuid import UUID

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import limiter
from services.chat_context_svc import ChatContextService, estimate_tokens
from services.chat_observability import ChatObservabilityService
from services.database import connect_sqlite
from services.openai_svc import ChatStreamError, OpenAIService
from services.sql_compat import current_date_expr, date_expr


chat_bp = Blueprint('chat', __name__)

MAX_MESSAGE_LENGTH = 2000
MAX_MESSAGES_PER_CONVERSATION = 100
MODEL_HISTORY_LIMIT = 20
HISTORY_RESPONSE_LIMIT = 50
DEFAULT_CHAT_MODEL = 'gpt-4o-mini'


def get_db() -> sqlite3.Connection:
    """Get a user-data connection for chat storage."""
    return connect_sqlite(current_app, log_label='Chat')


def _parse_conversation_id(raw_value: str | None) -> str | None:
    if not raw_value or not isinstance(raw_value, str):
        return None
    try:
        return str(UUID(raw_value))
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_request_id(raw_value: str | None) -> str | None:
    """Return a canonical retry key, or None for legacy callers."""
    if raw_value is None:
        return None
    return _parse_conversation_id(raw_value)


def _normalise_message(raw_message: str | None) -> str | None:
    if not isinstance(raw_message, str):
        return None
    message = raw_message.strip()
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        return None
    return message


def _token_count(text: str) -> int:
    return estimate_tokens(text)


def _is_missing_chat_table(exc: sqlite3.OperationalError) -> bool:
    return 'no such table: chat_messages' in str(exc).lower()


def _chat_rate_limit() -> str:
    return str(current_app.config['CHAT_RATE_LIMIT'])


def _chat_rate_limit_key() -> str:
    return str(get_jwt_identity())


def _chat_model() -> str:
    return os.getenv('CHAT_MODEL', DEFAULT_CHAT_MODEL)


def _chat_observer() -> ChatObservabilityService:
    return ChatObservabilityService(
        current_app.config['DATABASE_PATH'],
        log=current_app.logger,
    )


def _record_chat_event(**kwargs) -> None:
    _chat_observer().record_event(**kwargs)


def _daily_token_usage(conn: sqlite3.Connection, user_id: int) -> int:
    provider = current_app.config.get('DATABASE_PROVIDER', 'sqlite')
    created_date = date_expr('created_at', provider)
    current_date = current_date_expr(provider)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(token_count), 0) AS total
        FROM chat_messages
        WHERE user_id = ? AND {created_date} = {current_date}
        """,
        (user_id,),
    ).fetchone()
    return int(row['total'] or 0)


def _load_model_history(
    conn: sqlite3.Connection,
    user_id: int,
    conversation_id: str,
) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT role, content
        FROM (
            SELECT id, role, content
            FROM chat_messages
            WHERE user_id = ? AND conversation_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id ASC
        """,
        (user_id, conversation_id, MODEL_HISTORY_LIMIT),
    ).fetchall()
    return [{'role': row['role'], 'content': row['content']} for row in rows]


def _persist_message(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    conversation_id: str,
    role: str,
    content: str,
    request_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO chat_messages (
            user_id, conversation_id, request_id, role, content, token_count
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, conversation_id, request_id, role, content, _token_count(content)),
    )


def _load_request_messages(
    conn: sqlite3.Connection,
    user_id: int,
    request_id: str | None,
) -> dict[str, str]:
    if request_id is None:
        return {}
    rows = conn.execute(
        """
        SELECT role, content
        FROM chat_messages
        WHERE user_id = ? AND request_id = ?
        """,
        (user_id, request_id),
    ).fetchall()
    return {row['role']: row['content'] for row in rows}


def _prune_conversation(
    conn: sqlite3.Connection,
    user_id: int,
    conversation_id: str,
) -> None:
    conn.execute(
        """
        DELETE FROM chat_messages
        WHERE user_id = ?
          AND conversation_id = ?
          AND id NOT IN (
              SELECT id
              FROM chat_messages
              WHERE user_id = ? AND conversation_id = ?
              ORDER BY id DESC
              LIMIT ?
          )
        """,
        (user_id, conversation_id, user_id, conversation_id, MAX_MESSAGES_PER_CONVERSATION),
    )


def _sse_event(payload: dict[str, object]) -> str:
    return f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'


@chat_bp.route('/chat/message', methods=['POST'])
@jwt_required()
@limiter.limit(_chat_rate_limit, key_func=_chat_rate_limit_key)
def send_message():
    request_started_at = perf_counter()
    data = request.get_json(silent=True) or {}
    user_id = int(get_jwt_identity())
    conversation_id = _parse_conversation_id(data.get('conversation_id'))
    if conversation_id is None:
        _record_chat_event(
            event_type='validation_failed',
            user_id=user_id,
            error_code='invalid_conversation_id',
            model=_chat_model(),
        )
        return jsonify({'error': 'Invalid conversation_id'}), 400

    request_id = _parse_request_id(data.get('request_id'))
    if data.get('request_id') is not None and request_id is None:
        _record_chat_event(
            event_type='validation_failed',
            user_id=user_id,
            conversation_id=conversation_id,
            error_code='invalid_request_id',
            model=_chat_model(),
        )
        return jsonify({'error': 'Invalid request_id'}), 400

    message = _normalise_message(data.get('message'))
    if message is None:
        _record_chat_event(
            event_type='validation_failed',
            user_id=user_id,
            conversation_id=conversation_id,
            request_id=request_id,
            error_code='invalid_message',
            model=_chat_model(),
        )
        return jsonify({'error': 'Message must be non-empty and at most 2000 characters'}), 400

    database_path = current_app.config['DATABASE_PATH']
    input_tokens = _token_count(message)

    _record_chat_event(
        event_type='request_started',
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
        input_tokens=input_tokens,
        model=_chat_model(),
    )

    conn = get_db()
    try:
        existing_request = _load_request_messages(conn, user_id, request_id)
        if existing_request.get('user') not in (None, message):
            _record_chat_event(
                event_type='validation_failed',
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                error_code='request_id_conflict',
                input_tokens=input_tokens,
                model=_chat_model(),
            )
            return jsonify({'error': 'request_id is already used by another message'}), 409

        if 'user' not in existing_request:
            projected_usage = _daily_token_usage(conn, user_id) + input_tokens
            if projected_usage > current_app.config['CHAT_DAILY_TOKEN_BUDGET']:
                _record_chat_event(
                    event_type='token_budget_exceeded',
                    user_id=user_id,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    error_code='daily_token_budget_exceeded',
                    input_tokens=input_tokens,
                    model=_chat_model(),
                    metadata={'projected_usage': projected_usage},
                )
                return jsonify({'error': 'Daily chat limit reached. Resets at midnight.'}), 429

            _persist_message(
                conn,
                user_id=user_id,
                conversation_id=conversation_id,
                role='user',
                content=message,
                request_id=request_id,
            )
            conn.commit()
        model_history = _load_model_history(conn, user_id, conversation_id)
    except sqlite3.OperationalError as exc:
        if _is_missing_chat_table(exc):
            _record_chat_event(
                event_type='storage_unavailable',
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                error_code='chat_messages_missing',
                input_tokens=input_tokens,
                model=_chat_model(),
            )
            return jsonify({'error': 'chat storage not initialised'}), 503
        raise
    finally:
        conn.close()

    completed_reply = existing_request.get('assistant')
    if completed_reply is None:
        system_prompt = ChatContextService(database_path).build_system_prompt(user_id)
        model_stream = OpenAIService().chat_companion(
            messages=model_history,
            system_prompt=system_prompt,
        )
    else:
        model_stream = iter([completed_reply])

    @stream_with_context
    def generate_events() -> Iterator[str]:
        assistant_chunks: list[str] = []
        yield _sse_event({
            'chunk': '',
            'done': False,
            'event': 'started',
            'retry_after_ms': 1000,
        })
        try:
            for chunk in model_stream:
                if not chunk:
                    continue
                assistant_chunks.append(chunk)
                yield _sse_event({'chunk': chunk, 'done': False})

            assistant_reply = ''.join(assistant_chunks)
            if assistant_reply and completed_reply is None:
                stream_conn = get_db()
                try:
                    _persist_message(
                        stream_conn,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        role='assistant',
                        content=assistant_reply,
                        request_id=request_id,
                    )
                    _prune_conversation(stream_conn, user_id, conversation_id)
                    stream_conn.commit()
                finally:
                    stream_conn.close()

            yield _sse_event({
                'chunk': '',
                'done': True,
                'token_count': _token_count(assistant_reply),
            })
            _record_chat_event(
                event_type='completed',
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                latency_ms=round((perf_counter() - request_started_at) * 1000),
                input_tokens=input_tokens,
                output_tokens=_token_count(assistant_reply),
                model=_chat_model(),
                metadata={'replayed': completed_reply is not None},
            )
        except ChatStreamError:
            current_app.logger.exception('Chat response stream failed')
            _record_chat_event(
                event_type='failed',
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                error_code='provider_unavailable',
                latency_ms=round((perf_counter() - request_started_at) * 1000),
                input_tokens=input_tokens,
                output_tokens=_token_count(''.join(assistant_chunks)),
                model=_chat_model(),
            )
            yield _sse_event({
                'chunk': '',
                'done': True,
                'token_count': _token_count(''.join(assistant_chunks)),
                'error': 'The chat service is temporarily unavailable. Please try again.',
                'error_code': 'provider_unavailable',
                'retryable': True,
                'retry_after_ms': 1000,
            })
        except Exception:
            current_app.logger.exception('Unexpected chat response stream failure')
            _record_chat_event(
                event_type='failed',
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                error_code='stream_failed',
                latency_ms=round((perf_counter() - request_started_at) * 1000),
                input_tokens=input_tokens,
                output_tokens=_token_count(''.join(assistant_chunks)),
                model=_chat_model(),
            )
            yield _sse_event({
                'chunk': '',
                'done': True,
                'token_count': _token_count(''.join(assistant_chunks)),
                'error': 'The chat response could not be completed.',
                'error_code': 'stream_failed',
                'retryable': False,
            })

    return Response(
        generate_events(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@chat_bp.route('/chat/history', methods=['GET'])
@jwt_required()
def get_history():
    conversation_id = _parse_conversation_id(request.args.get('conversation_id'))
    if conversation_id is None:
        return jsonify({'error': 'Invalid conversation_id'}), 400

    user_id = int(get_jwt_identity())
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT role, content, token_count, created_at
            FROM (
                SELECT id, role, content, token_count, created_at
                FROM chat_messages
                WHERE user_id = ? AND conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (user_id, conversation_id, HISTORY_RESPONSE_LIMIT),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _is_missing_chat_table(exc):
            return jsonify({'error': 'chat storage not initialised'}), 503
        raise
    finally:
        conn.close()

    return jsonify({
        'conversation_id': conversation_id,
        'messages': [
            {
                'role': row['role'],
                'message': row['content'],
                'token_count': row['token_count'],
                'created_at': row['created_at'],
            }
            for row in rows
        ],
    }), 200


@chat_bp.route('/chat/conversation', methods=['DELETE'])
@jwt_required()
def clear_conversation():
    conversation_id = _parse_conversation_id(request.args.get('conversation_id'))
    if conversation_id is None:
        return jsonify({'error': 'Invalid conversation_id'}), 400

    user_id = int(get_jwt_identity())
    conn = get_db()
    try:
        conn.execute(
            'DELETE FROM chat_messages WHERE user_id = ? AND conversation_id = ?',
            (user_id, conversation_id),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        if _is_missing_chat_table(exc):
            return jsonify({'error': 'chat storage not initialised'}), 503
        raise
    finally:
        conn.close()

    return jsonify({'message': 'Conversation cleared'}), 200


@chat_bp.route('/chat/observability/report', methods=['GET'])
@jwt_required()
def get_chat_observability_report():
    try:
        days = int(request.args.get('days', '7'))
    except (TypeError, ValueError):
        return jsonify({'error': 'days must be a number'}), 400

    user_id = int(get_jwt_identity())
    try:
        report = _chat_observer().build_report(user_id=user_id, days=days)
    except sqlite3.OperationalError as exc:
        if 'no such table: chat_observability_events' in str(exc).lower():
            return jsonify({'error': 'chat observability not initialised'}), 503
        raise
    return jsonify(report), 200

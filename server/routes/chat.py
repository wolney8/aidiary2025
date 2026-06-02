"""Chat routes backed by SQLite chat_messages storage."""

import sqlite3
from uuid import UUID

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

chat_bp = Blueprint('chat', __name__)

MAX_MESSAGE_LENGTH = 2000
MAX_MESSAGES_PER_CONVERSATION = 100


def get_db() -> sqlite3.Connection:
    """Get database connection for chat storage."""
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_conversation_id(raw_value: str | None) -> str | None:
    if not raw_value or not isinstance(raw_value, str):
        return None
    try:
        return str(UUID(raw_value))
    except (ValueError, TypeError, AttributeError):
        return None


def _normalise_message(raw_message: str | None) -> str | None:
    if not isinstance(raw_message, str):
        return None
    message = raw_message.strip()
    if not message:
        return None
    if len(message) > MAX_MESSAGE_LENGTH:
        return None
    return message


def _assistant_placeholder_reply(message: str) -> str:
    # Deterministic response for first mergeable slice (no model call yet).
    preview = message[:160]
    return f"Assistant placeholder reply: {preview}"


def _token_count(text: str) -> int:
    return len(text.split())


def _is_missing_chat_table(exc: sqlite3.OperationalError) -> bool:
    return 'no such table: chat_messages' in str(exc).lower()


@chat_bp.route('/chat/message', methods=['POST'])
@jwt_required()
def send_message():
    data = request.get_json(silent=True) or {}
    conversation_id = _parse_conversation_id(data.get('conversation_id'))
    if conversation_id is None:
        return jsonify({'error': 'Invalid conversation_id'}), 400

    message = _normalise_message(data.get('message'))
    if message is None:
        return jsonify({'error': 'Message must be non-empty and at most 2000 characters'}), 400

    user_id = int(get_jwt_identity())
    assistant_reply = _assistant_placeholder_reply(message)

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            '''
            INSERT INTO chat_messages (user_id, conversation_id, role, content, token_count)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (user_id, conversation_id, 'user', message, _token_count(message)),
        )
        cursor.execute(
            '''
            INSERT INTO chat_messages (user_id, conversation_id, role, content, token_count)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (user_id, conversation_id, 'assistant', assistant_reply, _token_count(assistant_reply)),
        )

        # Keep storage bounded per conversation, preserving most recent messages.
        cursor.execute(
            '''
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
            ''',
            (user_id, conversation_id, user_id, conversation_id, MAX_MESSAGES_PER_CONVERSATION),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        if _is_missing_chat_table(exc):
            return jsonify({'error': 'chat storage not initialised'}), 503
        raise
    finally:
        conn.close()

    return jsonify({
        'conversation_id': conversation_id,
        'assistant_reply': assistant_reply,
    }), 200


@chat_bp.route('/chat/history', methods=['GET'])
@jwt_required()
def get_history():
    conversation_id = _parse_conversation_id(request.args.get('conversation_id'))
    if conversation_id is None:
        return jsonify({'error': 'Invalid conversation_id'}), 400

    user_id = int(get_jwt_identity())

    conn = get_db()
    cursor = conn.cursor()

    try:
        rows = cursor.execute(
            '''
            SELECT role, content
            FROM chat_messages
            WHERE user_id = ? AND conversation_id = ?
            ORDER BY created_at ASC, id ASC
            ''',
            (user_id, conversation_id),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if _is_missing_chat_table(exc):
            return jsonify({'error': 'chat storage not initialised'}), 503
        raise
    finally:
        conn.close()

    messages = [{'role': row['role'], 'message': row['content']} for row in rows]

    return jsonify({
        'conversation_id': conversation_id,
        'messages': messages,
    }), 200


@chat_bp.route('/chat/conversation', methods=['DELETE'])
@jwt_required()
def clear_conversation():
    conversation_id = _parse_conversation_id(request.args.get('conversation_id'))
    if conversation_id is None:
        return jsonify({'error': 'Invalid conversation_id'}), 400

    user_id = int(get_jwt_identity())

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
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
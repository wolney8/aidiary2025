"""Chat routes backed by temporary in-process memory storage."""

from threading import Lock
from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

chat_bp = Blueprint('chat', __name__)

MAX_MESSAGE_LENGTH = 2000
MAX_MESSAGES_PER_CONVERSATION = 100

# Keyed by (user_id, conversation_id)
_chat_store: dict[tuple[int, str], list[dict[str, str]]] = {}
_chat_store_lock = Lock()


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
    key = (user_id, conversation_id)

    with _chat_store_lock:
        messages = _chat_store.setdefault(key, [])
        messages.append({'role': 'user', 'message': message})
        messages.append({'role': 'assistant', 'message': assistant_reply})
        if len(messages) > MAX_MESSAGES_PER_CONVERSATION:
            _chat_store[key] = messages[-MAX_MESSAGES_PER_CONVERSATION:]

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
    key = (user_id, conversation_id)

    with _chat_store_lock:
        messages = list(_chat_store.get(key, []))

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
    key = (user_id, conversation_id)

    with _chat_store_lock:
        _chat_store.pop(key, None)

    return jsonify({'message': 'Conversation cleared'}), 200
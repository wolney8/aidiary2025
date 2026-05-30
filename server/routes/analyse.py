# server/routes/analyse.py
# AI analysis endpoint
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import sqlite3
from services.openai_svc import OpenAIService, AnalysisRateLimitError


def _normalise_people_names(raw: str) -> str:
    if not raw:
        return ""

    blocked = {
        "hopefully",
        "maybe",
        "someone",
        "somebody",
        "everyone",
        "everybody",
        "nobody",
        "anyone",
        "anybody",
        "person",
        "people",
        "friend",
        "friends",
        "unknown",
        "none",
        "na",
        "n/a",
    }

    cleaned = []
    for token in str(raw).split(","):
        candidate = token.strip()
        if not candidate:
            continue

        lower = candidate.lower()
        if lower in blocked:
            continue

        if not all(ch.isalpha() or ch in " -'" for ch in candidate):
            continue

        if len(candidate) < 2:
            continue

        cleaned.append(candidate)

    # Preserve ordering, drop duplicates.
    seen = set()
    ordered = []
    for item in cleaned:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)

    return ",".join(ordered)

analyse_bp = Blueprint('analyse', __name__)
ANALYSE_TEXT_MAX_LENGTH = 10000
RECENT_CONTEXT_MAX_ENTRIES = 5
RECENT_CONTEXT_MAX_ENTRY_CHARS = 500
RECENT_CONTEXT_MAX_TOTAL_CHARS = 1800


def get_db():
    """Get database connection."""
    db_path = current_app.config['DATABASE_PATH']
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def _truncate_text(value: str, max_chars: int) -> str:
    text = (value or '').strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + '...'


def _build_recent_context(user_id: int, mode: str) -> str | None:
    if mode == 'daily':
        query = """
            SELECT entry_date, entry_number, title, user_message
            FROM dailydiary_entries
            WHERE user_id = ?
            ORDER BY entry_date DESC, entry_number DESC, id DESC
            LIMIT ?
        """
        text_key = 'user_message'
    else:
        query = """
            SELECT entry_date, entry_number, title, plot, summary, interpretation
            FROM dreamdiary_entries
            WHERE user_id = ?
            ORDER BY entry_date DESC, entry_number DESC, id DESC
            LIMIT ?
        """
        text_key = 'plot'

    conn = get_db()
    try:
        rows = conn.execute(query, (user_id, RECENT_CONTEXT_MAX_ENTRIES)).fetchall()
    finally:
        conn.close()

    context_chunks: list[str] = []
    current_chars = 0

    for index, row in enumerate(rows, start=1):
        primary_text = row[text_key] if text_key in row.keys() else ''
        if mode == 'dream' and not primary_text:
            primary_text = row['summary'] or row['interpretation'] or ''

        snippet = _truncate_text(primary_text, RECENT_CONTEXT_MAX_ENTRY_CHARS)
        if not snippet:
            continue

        title = _truncate_text(row['title'] or '', 80)
        header = f"[{index}] date={row['entry_date'] or ''} entry={row['entry_number'] or ''}"
        if title:
            header += f" title={title}"

        section = f"{header}\n{snippet}"
        projected_chars = current_chars + len(section)
        if context_chunks:
            projected_chars += 2  # Extra separator between sections.

        if projected_chars > RECENT_CONTEXT_MAX_TOTAL_CHARS:
            break

        context_chunks.append(section)
        current_chars = projected_chars

    if not context_chunks:
        return None

    return "\n\n".join(context_chunks)

@analyse_bp.route('/analyse', methods=['POST'])
@jwt_required()
def analyse_text():
    """Analyse text using OpenAI and return structured insights."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400

    mode = data.get('mode', 'daily')  # 'daily' or 'dream'
    text = data.get('text', '')

    if mode not in ['daily', 'dream']:
        return jsonify({'error': 'Invalid mode. Use "daily" or "dream"'}), 400

    if not isinstance(text, str):
        return jsonify({'error': 'Text must be a string'}), 400

    text = text.strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if len(text) > ANALYSE_TEXT_MAX_LENGTH:
        return jsonify({'error': f'Text exceeds maximum length of {ANALYSE_TEXT_MAX_LENGTH} characters'}), 400

    recent_context = None
    try:
        user_id = int(get_jwt_identity())
        recent_context = _build_recent_context(user_id, mode)
    except Exception:
        current_app.logger.exception('Recent analysis context lookup failed; continuing without context')
    
    try:
        ai_service = OpenAIService()
        
        if mode == 'daily':
            result = ai_service.analyse_daily_entry(text, recent_context=recent_context)
            return jsonify({
                'ai_response': result['ai_response'],
                'tags': result['tags'],
                'daily_people_names': _normalise_people_names(result.get('people_names', '')),
                'daily_places': result['places']
            }), 200
        else:  # dream mode
            result = ai_service.analyse_dream_entry(text, recent_context=recent_context)
            return jsonify({
                'summary': result['summary'],
                'interpretation': result['interpretation'],
                'image_prompt': result['image_prompt'],
                'tags': result['tags'],
                'dream_people_names': _normalise_people_names(result.get('people_names', '')),
                'dream_places': result['places']
            }), 200
            
    except AnalysisRateLimitError:
        return jsonify({
            'error': 'AI analysis is temporarily rate-limited. Please try again later.',
            'code': 'rate_limited',
        }), 429
    except Exception:
        current_app.logger.exception('Analysis failed')
        return jsonify({'error': 'Analysis failed'}), 500
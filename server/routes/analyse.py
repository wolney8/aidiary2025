# server/routes/analyse.py
# AI analysis endpoint
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import difflib
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


def _compact_csv_hint(raw: object, label: str, max_items: int = 3, max_chars: int = 60) -> str:
    if not isinstance(raw, str):
        return ''

    items: list[str] = []
    seen: set[str] = set()
    for token in raw.split(','):
        candidate = token.strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(candidate)
        if len(items) >= max_items:
            break

    if not items:
        return ''

    value = ', '.join(items)
    value = _truncate_text(value, max_chars)
    return f"{label}:{value}"


def _normalise_header_for_similarity(value: str) -> str:
    return ' '.join((value or '').strip().lower().split())


def _is_highly_similar_header(value: str, existing_values: list[str]) -> bool:
    normalised = _normalise_header_for_similarity(value)
    if not normalised:
        return True

    for existing in existing_values:
        existing_normalised = _normalise_header_for_similarity(existing)
        if normalised == existing_normalised:
            return True

        ratio = difflib.SequenceMatcher(None, normalised, existing_normalised).ratio()
        if ratio >= 0.93:
            return True

    return False


def _validate_reference_date(value: object) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError('reference_date must be formatted as YYYY-MM-DD')

    candidate = value.strip()
    if not candidate:
        return None

    try:
        datetime.strptime(candidate, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('reference_date must be formatted as YYYY-MM-DD') from exc

    return candidate


def _build_metadata_summary_header(mode: str, text: str, result: dict) -> str:
    if mode == 'daily':
        source = result.get('ai_response') or text
    else:
        source = result.get('summary') or result.get('interpretation') or text

    base = _truncate_text(str(source or ''), 220)
    hints = [
        _compact_csv_hint(result.get('tags', ''), 'tags', max_items=3, max_chars=40),
        _compact_csv_hint(result.get('people_names', ''), 'people', max_items=2, max_chars=36),
        _compact_csv_hint(result.get('places', ''), 'places', max_items=2, max_chars=36),
    ]
    hint_text = ' | '.join(hint for hint in hints if hint)
    if not hint_text:
        return _truncate_text(base, 280)
    return _truncate_text(f"{base} | {hint_text}", 280)


def _persist_analysis_metadata(
    user_id: int,
    mode: str,
    reference_date: str | None,
    summary_header: str,
    tags: str,
    people_names: str,
    places: str,
) -> None:
    conn = get_db()
    try:
        conn.execute(
            """
            INSERT INTO entry_ai_metadata (
                user_id, mode, reference_date, summary_header, tags, people_names, places
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, mode, reference_date, summary_header, tags, people_names, places),
        )
        conn.commit()
    except Exception:
        current_app.logger.exception('Failed to persist analysis metadata; continuing')
    finally:
        conn.close()


def _build_recent_context(user_id: int, mode: str, reference_date: str | None = None) -> str | None:
    conn = get_db()

    metadata_rows = []
    try:
        metadata_query = """
            SELECT reference_date, summary_header
            FROM entry_ai_metadata
            WHERE user_id = ?
              AND mode = ?
        """
        metadata_params: list[object] = [user_id, mode]

        if reference_date:
            metadata_query += """
                ORDER BY
                    CASE WHEN reference_date IS NULL THEN 1 ELSE 0 END,
                    ABS(julianday(reference_date) - julianday(?)) ASC,
                    reference_date DESC,
                    id DESC
            """
            metadata_params.append(reference_date)
        else:
            metadata_query += " ORDER BY reference_date DESC, id DESC"

        metadata_query += " LIMIT ?"
        metadata_params.append(RECENT_CONTEXT_MAX_ENTRIES * 3)

        metadata_rows = conn.execute(metadata_query, tuple(metadata_params)).fetchall()
    except sqlite3.OperationalError:
        metadata_rows = []

    if metadata_rows:
        context_chunks: list[str] = []
        selected_headers: list[str] = []
        current_chars = 0

        for index, row in enumerate(metadata_rows, start=1):
            snippet = _truncate_text(row['summary_header'] or '', RECENT_CONTEXT_MAX_ENTRY_CHARS)
            if not snippet:
                continue

            if _is_highly_similar_header(snippet, selected_headers):
                continue

            selected_headers.append(snippet)

            header = f"[{len(context_chunks) + 1}] ref_date={row['reference_date'] or ''}"
            section = f"{header}\n{snippet}"
            projected_chars = current_chars + len(section)
            if context_chunks:
                projected_chars += 2

            if projected_chars > RECENT_CONTEXT_MAX_TOTAL_CHARS:
                break

            context_chunks.append(section)
            current_chars = projected_chars

            if len(context_chunks) >= RECENT_CONTEXT_MAX_ENTRIES:
                break

        if context_chunks:
            conn.close()
            return "\n\n".join(context_chunks)

    if mode == 'daily':
        query = """
            SELECT entry_date, entry_number, title, user_message
            FROM dailydiary_entries
            WHERE user_id = ?
              AND (? IS NULL OR entry_date <= ?)
            ORDER BY entry_date DESC, entry_number DESC, id DESC
            LIMIT ?
        """
        text_key = 'user_message'
        params = (user_id, reference_date, reference_date, RECENT_CONTEXT_MAX_ENTRIES)
    else:
        query = """
            SELECT entry_date, entry_number, title, plot, summary, interpretation
            FROM dreamdiary_entries
            WHERE user_id = ?
              AND (? IS NULL OR entry_date <= ?)
            ORDER BY entry_date DESC, entry_number DESC, id DESC
            LIMIT ?
        """
        text_key = 'plot'
        params = (user_id, reference_date, reference_date, RECENT_CONTEXT_MAX_ENTRIES)

    try:
        rows = conn.execute(query, params).fetchall()
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
    reference_date_raw = data.get('reference_date')

    if mode not in ['daily', 'dream']:
        return jsonify({'error': 'Invalid mode. Use "daily" or "dream"'}), 400

    if not isinstance(text, str):
        return jsonify({'error': 'Text must be a string'}), 400

    text = text.strip()
    if not text:
        return jsonify({'error': 'Text is required'}), 400

    if len(text) > ANALYSE_TEXT_MAX_LENGTH:
        return jsonify({'error': f'Text exceeds maximum length of {ANALYSE_TEXT_MAX_LENGTH} characters'}), 400

    try:
        reference_date = _validate_reference_date(reference_date_raw)
    except ValueError:
        return jsonify({'error': 'Invalid reference_date format. Use YYYY-MM-DD'}), 400

    recent_context = None
    user_id = None
    try:
        user_id = int(get_jwt_identity())
        recent_context = _build_recent_context(user_id, mode, reference_date)
    except Exception:
        current_app.logger.exception('Recent analysis context lookup failed; continuing without context')
    
    try:
        ai_service = OpenAIService()
        
        if mode == 'daily':
            result = ai_service.analyse_daily_entry(text, recent_context=recent_context)
            if user_id is not None:
                _persist_analysis_metadata(
                    user_id=user_id,
                    mode=mode,
                    reference_date=reference_date,
                    summary_header=_build_metadata_summary_header(mode, text, result),
                    tags=str(result.get('tags', '')),
                    people_names=_normalise_people_names(result.get('people_names', '')),
                    places=str(result.get('places', '')),
                )
            return jsonify({
                'ai_response': result['ai_response'],
                'tags': result['tags'],
                'daily_people_names': _normalise_people_names(result.get('people_names', '')),
                'daily_places': result['places']
            }), 200
        else:  # dream mode
            result = ai_service.analyse_dream_entry(text, recent_context=recent_context)
            if user_id is not None:
                _persist_analysis_metadata(
                    user_id=user_id,
                    mode=mode,
                    reference_date=reference_date,
                    summary_header=_build_metadata_summary_header(mode, text, result),
                    tags=str(result.get('tags', '')),
                    people_names=_normalise_people_names(result.get('people_names', '')),
                    places=str(result.get('places', '')),
                )
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
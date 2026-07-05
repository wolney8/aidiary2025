# server/routes/analyse.py
# AI analysis endpoint
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
import difflib
import re
import sqlite3
from services.attachment_text import (
    extract_pdf_attachment_content,
    looks_like_low_quality_ocr_text,
)
from services.ai_config import DEFAULT_ANALYSIS_MODEL
from services.media_storage import read_media_bytes
from services.openai_svc import OpenAIService, AnalysisRateLimitError
from services.nltk_enrichment import (
    derive_daily_nltk_fields,
    derive_dream_nltk_fields,
    merge_csv_values,
)


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


def _normalise_places(raw: str) -> str:
    if not raw:
        return ""

    cleaned: list[str] = []
    seen: set[str] = set()
    for token in str(raw).split(","):
        candidate = token.strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)

    return ",".join(cleaned)


def _normalise_tags(raw: str) -> str:
    if not raw:
        return ""

    blocked = {
        "analysis",
        "analysed",
        "analyzed",
        "ai",
        "response",
        "entry",
        "entries",
        "daily",
        "dream",
    }

    cleaned: list[str] = []
    seen: set[str] = set()
    for token in str(raw).split(","):
        candidate = token.strip().lower()
        if not candidate:
            continue
        if candidate in blocked:
            continue
        if len(candidate) < 2:
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9 _'/-]{0,39}", candidate):
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)

    return ",".join(cleaned)


def _format_human_reference_date(value: str | None) -> str:
    if not value:
        return 'an earlier date'

    try:
        parsed = datetime.strptime(str(value), '%Y-%m-%d')
    except (TypeError, ValueError):
        return str(value)

    return f'{parsed.day} {parsed.strftime("%B %Y")}'

analyse_bp = Blueprint('analyse', __name__)
ANALYSE_TEXT_MAX_LENGTH = 10000
RECENT_CONTEXT_MAX_ENTRIES = 5
RECENT_CONTEXT_MAX_ENTRY_CHARS = 500
RECENT_CONTEXT_MAX_TOTAL_CHARS = 1800
ATTACHMENT_CONTEXT_MAX_CHARS = 900
RELATED_CONTEXT_MAX_ENTRIES = 3
RELATED_CONTEXT_SCAN_LIMIT = 24
LEXICAL_STOP_WORDS = {
    'the', 'and', 'that', 'with', 'from', 'have', 'this', 'your', 'about',
    'were', 'when', 'then', 'just', 'into', 'there', 'their', 'would', 'could',
    'should', 'been', 'after', 'before', 'because', 'while', 'what', 'where',
    'which', 'they', 'them', 'felt', 'feel', 'like', 'today', 'dream', 'daily',
    'entry', 'very', 'really', 'some', 'more', 'than', 'also', 'only', 'over',
}
DEFAULT_ANALYSIS_SETTINGS = {
    'ai_tone': 'friendly',
    'ai_verbosity': 'balanced',
    'ai_focus': 'reflective',
    'ai_model': DEFAULT_ANALYSIS_MODEL,
    'allow_ai_history': True,
    'personal_context': None,
}


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


def _parse_csv_tokens(raw: object) -> list[str]:
    if not isinstance(raw, str):
        return []

    values: list[str] = []
    seen: set[str] = set()
    for token in raw.split(','):
        candidate = token.strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(candidate)

    return values


def _tokenise_similarity_text(*parts: object) -> set[str]:
    combined = ' '.join(str(part or '') for part in parts)
    tokens = {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z'-]{2,}", combined.lower())
        if token not in LEXICAL_STOP_WORDS
    }
    return tokens


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


def _load_user_analysis_settings(conn: sqlite3.Connection, user_id: int) -> dict[str, object]:
    settings = dict(DEFAULT_ANALYSIS_SETTINGS)
    try:
        row = conn.execute(
            '''
            SELECT ai_tone, ai_verbosity, ai_focus, ai_model, allow_ai_history,
                   display_name, pronouns, gender, custom_guidance, sex, goals
            FROM users
            WHERE id = ?
            ''',
            (user_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return settings

    if not row:
        return settings

    settings['ai_tone'] = str(row['ai_tone'] or settings['ai_tone']).strip() or settings['ai_tone']
    settings['ai_verbosity'] = str(row['ai_verbosity'] or settings['ai_verbosity']).strip() or settings['ai_verbosity']
    settings['ai_focus'] = str(row['ai_focus'] or settings['ai_focus']).strip() or settings['ai_focus']
    settings['ai_model'] = str(row['ai_model'] or settings['ai_model']).strip() or settings['ai_model']
    settings['allow_ai_history'] = bool(row['allow_ai_history']) if row['allow_ai_history'] is not None else True
    personal_bits: list[str] = []
    display_name = str(row['display_name'] or '').strip()
    pronouns = str(row['pronouns'] or '').strip()
    gender = str(row['gender'] or row['sex'] or '').strip()
    custom_guidance = str(row['custom_guidance'] or row['goals'] or '').strip()

    if display_name:
        personal_bits.append(f'Display name: {display_name}')
    if pronouns:
        personal_bits.append(f'Pronouns: {pronouns}')
    if gender:
        personal_bits.append(f'Gender: {gender}')
    if custom_guidance:
        personal_bits.append(f'Custom guidance: {custom_guidance}')

    settings['personal_context'] = '\n'.join(personal_bits) if personal_bits else None
    return settings


def _load_current_entry_memory_details(
    conn: sqlite3.Connection,
    user_id: int,
    mode: str,
    entry_id: int | None,
) -> dict[str, object] | None:
    if entry_id is None:
        return None

    if mode == 'daily':
        query = '''
            SELECT id, title, tags, daily_people_names AS people_names, daily_places AS places, user_message AS body
            FROM dailydiary_entries
            WHERE user_id = ? AND id = ?
        '''
    else:
        query = '''
            SELECT id, title, tags, dream_people_names AS people_names, dream_places AS places, plot AS body
            FROM dreamdiary_entries
            WHERE user_id = ? AND id = ?
        '''

    row = conn.execute(query, (user_id, entry_id)).fetchone()
    return dict(row) if row else None


def _merge_daily_analysis_with_nltk(text: str, result: dict) -> dict[str, str]:
    user_nltk = derive_daily_nltk_fields("", text)
    ai_nltk = derive_daily_nltk_fields("", str(result.get("ai_response", "")))

    merged_people = _normalise_people_names(
        merge_csv_values(
            user_nltk.get("daily_people_names", ""),
            str(result.get("people_names", "")),
        )
    )
    merged_places = _normalise_places(
        merge_csv_values(
            user_nltk.get("daily_places", ""),
            str(result.get("places", "")),
        )
    )
    merged_tags = _normalise_tags(
        merge_csv_values(
            user_nltk.get("tags", ""),
            str(result.get("tags", "")),
            ai_nltk.get("tags", ""),
        )
    )

    return {
        "ai_response": str(result.get("ai_response", "")),
        "tags": merged_tags,
        "people_names": merged_people,
        "places": merged_places,
    }


def _merge_dream_analysis_with_nltk(text: str, result: dict) -> dict[str, str]:
    user_nltk = derive_dream_nltk_fields(
        {
            "title": "",
            "plot": text,
            "cast": "",
            "symbols_and_imagery": "",
            "insight": "",
            "action": "",
            "other": "",
            "tags": "",
        }
    )
    ai_nltk = derive_dream_nltk_fields(
        {
            "title": "",
            "plot": str(result.get("summary", "")),
            "cast": "",
            "symbols_and_imagery": "",
            "insight": str(result.get("interpretation", "")),
            "action": "",
            "other": "",
            "tags": "",
        }
    )

    merged_people = _normalise_people_names(
        merge_csv_values(
            user_nltk.get("dream_people_names", ""),
            str(result.get("people_names", "")),
        )
    )
    merged_places = _normalise_places(
        merge_csv_values(
            user_nltk.get("dream_places", ""),
            str(result.get("places", "")),
        )
    )
    merged_tags = _normalise_tags(
        merge_csv_values(
            user_nltk.get("tags", ""),
            str(result.get("tags", "")),
            ai_nltk.get("tags", ""),
        )
    )

    return {
        "summary": str(result.get("summary", "")),
        "interpretation": str(result.get("interpretation", "")),
        "image_prompt": str(result.get("image_prompt", "")),
        "tags": merged_tags,
        "people_names": merged_people,
        "places": merged_places,
    }


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


def _build_related_history_context(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    mode: str,
    current_text: str,
    current_entry_id: int | None,
    reference_date: str | None,
) -> str | None:
    current_entry = _load_current_entry_memory_details(conn, user_id, mode, current_entry_id)
    current_title = str((current_entry or {}).get('title') or '')
    current_tags = set(token.lower() for token in _parse_csv_tokens((current_entry or {}).get('tags')))
    current_people = set(token.lower() for token in _parse_csv_tokens((current_entry or {}).get('people_names')))
    current_places = set(token.lower() for token in _parse_csv_tokens((current_entry or {}).get('places')))
    current_tokens = _tokenise_similarity_text(current_text, current_title, (current_entry or {}).get('body', ''))

    if mode == 'daily':
        rows = conn.execute(
            '''
            SELECT id, entry_date, entry_number, title, user_message AS body,
                   tags, daily_people_names AS people_names, daily_places AS places
            FROM dailydiary_entries
            WHERE user_id = ?
              AND (? IS NULL OR entry_date <= ?)
              AND (? IS NULL OR id != ?)
            ORDER BY entry_date DESC, entry_number DESC, id DESC
            LIMIT ?
            ''',
            (user_id, reference_date, reference_date, current_entry_id, current_entry_id, RELATED_CONTEXT_SCAN_LIMIT),
        ).fetchall()
    else:
        rows = conn.execute(
            '''
            SELECT id, entry_date, entry_number, title,
                   COALESCE(plot, summary, interpretation, '') AS body,
                   tags, dream_people_names AS people_names, dream_places AS places
            FROM dreamdiary_entries
            WHERE user_id = ?
              AND (? IS NULL OR entry_date <= ?)
              AND (? IS NULL OR id != ?)
            ORDER BY entry_date DESC, entry_number DESC, id DESC
            LIMIT ?
            ''',
            (user_id, reference_date, reference_date, current_entry_id, current_entry_id, RELATED_CONTEXT_SCAN_LIMIT),
        ).fetchall()

    ranked: list[tuple[float, sqlite3.Row, dict[str, list[str] | float]]] = []
    for row in rows:
        row_tags = _parse_csv_tokens(row['tags'])
        row_people = _parse_csv_tokens(row['people_names'])
        row_places = _parse_csv_tokens(row['places'])
        row_tokens = _tokenise_similarity_text(row['title'], row['body'])

        tag_overlap = sorted(current_tags.intersection(token.lower() for token in row_tags))
        people_overlap = sorted(current_people.intersection(token.lower() for token in row_people))
        place_overlap = sorted(current_places.intersection(token.lower() for token in row_places))
        lexical_overlap = sorted(current_tokens.intersection(row_tokens))

        score = (
            len(people_overlap) * 5.0 +
            len(tag_overlap) * 4.0 +
            len(place_overlap) * 4.0 +
            min(len(lexical_overlap), 5) * 1.3
        )
        if score <= 0:
            continue

        if reference_date and row['entry_date']:
            try:
                distance = abs((datetime.strptime(reference_date, '%Y-%m-%d') - datetime.strptime(row['entry_date'], '%Y-%m-%d')).days)
                score += max(0.0, 1.5 - min(distance, 30) / 20.0)
            except ValueError:
                pass

        ranked.append((
            score,
            row,
            {
                'tags': tag_overlap,
                'people': people_overlap,
                'places': place_overlap,
                'lexical_overlap': lexical_overlap,
            },
        ))

    ranked.sort(key=lambda item: (item[0], str(item[1]['entry_date'] or '')), reverse=True)
    if not ranked:
        return None

    context_chunks: list[str] = []
    current_chars = 0
    for index, (_score, row, overlaps) in enumerate(ranked[:RELATED_CONTEXT_MAX_ENTRIES], start=1):
        theme_candidates = overlaps['people'][:1] + overlaps['tags'][:2] + overlaps['places'][:1]
        theme_text = ', '.join(theme_candidates[:3]) or ', '.join(overlaps['lexical_overlap'][:3]) or 'related pattern'
        snippet = _truncate_text(str(row['body'] or ''), 240)
        title = _truncate_text(str(row['title'] or ''), 80)
        date_label = _format_human_reference_date(row['entry_date'])
        header = f"[related {index}] On {date_label}, shared theme: {theme_text}"
        if title:
            header += f" | title: {title}"
        section = f"{header}\nSnapshot: {snippet}"
        projected_chars = current_chars + len(section) + (2 if context_chunks else 0)
        if projected_chars > RECENT_CONTEXT_MAX_TOTAL_CHARS:
            break
        context_chunks.append(section)
        current_chars = projected_chars

    if not context_chunks:
        return None

    return "Related entry memory:\n" + "\n\n".join(context_chunks)


def _build_attachment_ref_label(
    filename: str,
    mime_type: str,
    *,
    has_derived_text: bool,
    derived_text_source: str = '',
) -> str:
    if mime_type == 'application/pdf' and has_derived_text:
        if derived_text_source == 'pdf-ocr':
            return f'{filename} (PDF OCR text)'
        return f'{filename} (PDF text extracted)'
    if mime_type == 'application/pdf':
        return f'{filename} (PDF filename only)'
    if mime_type.startswith('audio/') and has_derived_text:
        return f'{filename} (audio transcript)'
    if mime_type.startswith('audio/'):
        return f'{filename} (audio filename only)'
    if mime_type.startswith('image/'):
        return f'{filename} (image reference)'
    return f'{filename} (filename reference)'


def _build_attachment_context(user_id: int, mode: str, entry_id: int) -> tuple[str | None, list[str]]:
    entry_type = 'daily' if mode == 'daily' else 'dream'
    conn = get_db()
    try:
        rows = conn.execute(
            '''
            SELECT id, storage_key, original_filename, mime_type, derived_text, derived_text_source
            FROM entry_assets
            WHERE user_id = ? AND entry_type = ? AND entry_id = ?
            ORDER BY sort_order ASC, id ASC
            LIMIT 3
            ''',
            (user_id, entry_type, entry_id),
        ).fetchall()

        if not rows:
            return None, []

        lines: list[str] = []
        refs: list[str] = []
        current_chars = 0
        did_update = False
        for row in rows:
            mime_type = str(row['mime_type'] or '').strip().lower()
            if mime_type.startswith('audio/'):
                type_label = 'audio attachment'
            elif mime_type == 'application/pdf':
                type_label = 'PDF attachment'
            elif mime_type.startswith('image/'):
                type_label = 'image attachment'
            else:
                type_label = 'attachment'

            filename = str(row['original_filename'] or 'attachment').strip() or 'attachment'
            derived_text_raw = str(row['derived_text'] or '').strip()
            derived_text_source = str(row['derived_text_source'] or '').strip()
            should_refresh_pdf_text = (
                mime_type == 'application/pdf' and (
                    not derived_text_raw
                    or (
                        derived_text_source == 'pdf-ocr'
                        and looks_like_low_quality_ocr_text(derived_text_raw)
                    )
                )
            )
            if should_refresh_pdf_text:
                file_bytes = read_media_bytes(str(row['storage_key'] or '').strip())
                extracted_text, extracted_text_source = extract_pdf_attachment_content(file_bytes or b'')
                if extracted_text:
                    if extracted_text_source == 'pdf-ocr':
                        try:
                            extracted_text = OpenAIService().clean_ocr_extracted_text(extracted_text)
                        except AnalysisRateLimitError:
                            current_app.logger.warning(
                                'PDF OCR cleanup rate-limited during analysis for %s attachment "%s"; using raw OCR text.',
                                entry_type,
                                filename,
                            )
                        except Exception:
                            current_app.logger.exception(
                                'PDF OCR cleanup failed during analysis for %s attachment "%s"; using raw OCR text.',
                                entry_type,
                                filename,
                            )
                    derived_text_raw = extracted_text
                    derived_text_source = extracted_text_source or 'pdf-text-extraction'
                    conn.execute(
                        '''
                        UPDATE entry_assets
                        SET derived_text = ?, derived_text_source = ?, derived_text_updated_at = ?
                        WHERE id = ? AND user_id = ?
                        ''',
                        (
                            extracted_text,
                            derived_text_source,
                            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            int(row['id']),
                            user_id,
                        ),
                    )
                    did_update = True
            else:
                derived_text_source = ''

            line = f'- Your {type_label} "{filename}"'
            derived_text = _truncate_text(derived_text_raw, 260)
            if derived_text:
                line += f"\n  Derived text summary: {derived_text}"
            projected = current_chars + len(line) + (1 if lines else 0)
            if projected > ATTACHMENT_CONTEXT_MAX_CHARS:
                break
            refs.append(
                _build_attachment_ref_label(
                    filename,
                    mime_type,
                    has_derived_text=bool(derived_text_raw),
                    derived_text_source=derived_text_source,
                )
            )
            lines.append(line)
            current_chars = projected

        if did_update:
            conn.commit()

        if not lines:
            return None, refs

        return "Attachment context:\n" + "\n".join(lines), refs
    finally:
        conn.close()


def _merge_analysis_context(
    recent_context: str | None,
    attachment_context: str | None,
) -> str | None:
    parts = [
        part.strip()
        for part in (recent_context, attachment_context)
        if isinstance(part, str) and part.strip()
    ]
    if not parts:
        return None
    return "\n\n".join(parts)

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
    entry_id_raw = data.get('entry_id')
    include_attachment_context = bool(data.get('include_attachment_context'))
    ai_style = str(data.get('ai_style') or 'friendly').strip() or 'friendly'

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

    entry_id = None
    if entry_id_raw is not None:
        try:
            entry_id = int(entry_id_raw)
        except (TypeError, ValueError):
            if not include_attachment_context:
                entry_id = None
            else:
                return jsonify({'error': 'entry_id is required when include_attachment_context is enabled'}), 400
    if include_attachment_context and entry_id is None:
        try:
            entry_id = int(entry_id_raw)
        except (TypeError, ValueError):
            return jsonify({'error': 'entry_id is required when include_attachment_context is enabled'}), 400

    related_context = None
    attachment_context = None
    attachment_context_refs: list[str] = []
    user_id = None
    analysis_settings = dict(DEFAULT_ANALYSIS_SETTINGS)
    try:
        user_id = int(get_jwt_identity())
        conn = get_db()
        try:
            analysis_settings = _load_user_analysis_settings(conn, user_id)
            if bool(analysis_settings.get('allow_ai_history')):
                related_context = _build_related_history_context(
                    conn,
                    user_id=user_id,
                    mode=mode,
                    current_text=text,
                    current_entry_id=entry_id,
                    reference_date=reference_date,
                )
        finally:
            conn.close()
        if include_attachment_context and entry_id is not None:
            attachment_context, attachment_context_refs = _build_attachment_context(user_id, mode, entry_id)
        recent_context = _merge_analysis_context(related_context, attachment_context)
    except Exception:
        current_app.logger.exception('Recent analysis context lookup failed; continuing without context')
        recent_context = _merge_analysis_context(related_context, attachment_context)

    try:
        ai_service = OpenAIService()
        analysis_options = {
            'ai_style': ai_style,
            'ai_tone': analysis_settings.get('ai_tone', DEFAULT_ANALYSIS_SETTINGS['ai_tone']),
            'ai_verbosity': analysis_settings.get('ai_verbosity', DEFAULT_ANALYSIS_SETTINGS['ai_verbosity']),
            'ai_focus': analysis_settings.get('ai_focus', DEFAULT_ANALYSIS_SETTINGS['ai_focus']),
            'ai_model': analysis_settings.get('ai_model', DEFAULT_ANALYSIS_SETTINGS['ai_model']),
            'has_related_context': bool(related_context),
            'has_attachment_context': bool(attachment_context),
            'personal_context': analysis_settings.get('personal_context'),
        }
        
        if mode == 'daily':
            result = ai_service.analyse_daily_entry(
                text,
                recent_context=recent_context,
                related_context=related_context,
                attachment_context=attachment_context,
                analysis_options=analysis_options,
            )
            merged_result = _merge_daily_analysis_with_nltk(text, result)
            if user_id is not None:
                _persist_analysis_metadata(
                    user_id=user_id,
                    mode=mode,
                    reference_date=reference_date,
                    summary_header=_build_metadata_summary_header(mode, text, merged_result),
                    tags=str(merged_result.get('tags', '')),
                    people_names=_normalise_people_names(merged_result.get('people_names', '')),
                    places=str(merged_result.get('places', '')),
                )
            return jsonify({
                'ai_response': merged_result['ai_response'],
                'tags': merged_result['tags'],
                'daily_people_names': _normalise_people_names(merged_result.get('people_names', '')),
                'daily_places': merged_result['places'],
                **(
                    {'attachment_context_refs': attachment_context_refs}
                    if include_attachment_context
                    else {}
                ),
            }), 200
        else:  # dream mode
            result = ai_service.analyse_dream_entry(
                text,
                recent_context=recent_context,
                related_context=related_context,
                attachment_context=attachment_context,
                analysis_options=analysis_options,
            )
            merged_result = _merge_dream_analysis_with_nltk(text, result)
            if user_id is not None:
                _persist_analysis_metadata(
                    user_id=user_id,
                    mode=mode,
                    reference_date=reference_date,
                    summary_header=_build_metadata_summary_header(mode, text, merged_result),
                    tags=str(merged_result.get('tags', '')),
                    people_names=_normalise_people_names(merged_result.get('people_names', '')),
                    places=str(merged_result.get('places', '')),
                )
            return jsonify({
                'summary': merged_result['summary'],
                'interpretation': merged_result['interpretation'],
                'image_prompt': merged_result['image_prompt'],
                'tags': merged_result['tags'],
                'dream_people_names': _normalise_people_names(merged_result.get('people_names', '')),
                'dream_places': merged_result['places'],
                **(
                    {'attachment_context_refs': attachment_context_refs}
                    if include_attachment_context
                    else {}
                ),
            }), 200
            
    except AnalysisRateLimitError:
        return jsonify({
            'error': 'AI analysis is temporarily rate-limited. Please try again later.',
            'code': 'rate_limited',
        }), 429
    except Exception:
        current_app.logger.exception('Analysis failed')
        return jsonify({'error': 'Analysis failed'}), 500

# server/routes/entries.py
# CRUD routes for diary entries
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import json
import os
import sqlite3
from datetime import date, datetime, timezone
import re
from html import escape
from io import BytesIO
from services.import_service import (
    ensure_export_history_table,
    get_latest_bulk_delete_guard,
    mark_export_guard_used,
)
from services.nltk_enrichment import (
    derive_daily_nltk_fields,
    derive_dream_nltk_fields,
    merge_csv_values,
)
from services.attachment_text import (
    extract_pdf_attachment_content,
    looks_like_low_quality_ocr_text,
)
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.sql_compat import adapt_placeholders, append_returning_id, inserted_id
from services.openai_svc import (
    DAILY_IMAGE_STYLE_PREFIX,
    DREAM_IMAGE_STYLE_PREFIX,
    AnalysisRateLimitError,
    OpenAIService,
)
from services.media_storage import (
    delete_image,
    is_legacy_data_url,
    media_path_exists,
    migrate_legacy_data_url,
    read_image_bytes,
    resolve_image_url,
    store_entry_asset,
    store_generated_image,
    store_uploaded_image,
)
from services.usage_limits import (
    AI_IMAGE_EVENT,
    OCR_PAGE_EVENT,
    TRANSCRIPTION_MINUTE_EVENT,
    UsageLimitExceeded,
    enforce_storage_limit,
    enforce_usage_limit,
    record_usage_event,
)
from routes.cbt import _serialise_worksheet, _worksheet_query
from routes.important_days import IMPORTANT_DAY_SELECT, _serialise_important_day
from PIL import Image, ImageOps, UnidentifiedImageError

entries_bp = Blueprint('entries', __name__)

ALLOWED_ENTRY_IMAGE_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
}
ALLOWED_ENTRY_ATTACHMENT_MIME_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf',
    'audio/mpeg',
    'audio/mp3',
    'audio/wav',
    'audio/x-wav',
    'audio/ogg',
    'audio/mp4',
    'audio/x-m4a',
    'audio/webm',
    'audio/aiff',
    'audio/x-aiff',
}
MAX_ENTRY_IMAGE_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ENTRY_ATTACHMENT_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_ENTRY_IMAGE_OR_PDF_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ENTRY_AUDIO_ATTACHMENT_BYTES = 25 * 1024 * 1024
MAX_ATTACHMENTS_PER_ENTRY = 3
ENTRY_IMAGE_TARGET_SIZE = (933, 705)
ENTRY_IMAGE_JPEG_QUALITY = 85
SEARCH_RESULT_LIMIT = 250


def _quota_exceeded_payload(exc: UsageLimitExceeded, message: str) -> tuple[dict, int]:
    return {
        'error': message,
        'code': 'upgrade_required',
        'usage': exc.summary,
    }, 402


def _check_usage_or_error(conn, *, user_id: int, event_type: str, units: int, message: str):
    try:
        enforce_usage_limit(conn, user_id=user_id, event_type=event_type, units=units)
    except UsageLimitExceeded as exc:
        return _quota_exceeded_payload(exc, message)
    except Exception:
        current_app.logger.exception('Usage check failed for event %s', event_type)
        return {'error': 'Usage could not be checked. Please try again.'}, 503
    return None


def _record_usage_safely(
    conn,
    *,
    user_id: int,
    event_type: str,
    units: int = 1,
    metadata: dict | None = None,
) -> None:
    try:
        record_usage_event(
            conn,
            user_id=user_id,
            event_type=event_type,
            units=units,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning('Usage event could not be recorded for %s: %s', event_type, exc)


def get_db():
    """Get database connection."""
    return _database_adapter().open(
        timeout=30,
        journal_mode_wal=True,
    )


def _database_adapter() -> DatabaseAdapter:
    return current_app.config['DATABASE_ADAPTER']


def _database_provider() -> str:
    return current_app.config.get('DATABASE_PROVIDER', SQLITE_PROVIDER)


def _sql(statement: str) -> str:
    return adapt_placeholders(statement, _database_provider())


def _parse_entry_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        try:
            return datetime.strptime(str(value), '%Y-%m-%d')
        except (TypeError, ValueError):
            return None


def _format_date_strings(date_obj):
    if not date_obj:
        return []
    return [
        date_obj.strftime('%d/%m/%Y'),
        date_obj.strftime('%A %d %B %Y'),
        date_obj.strftime('%d %B %Y'),
        date_obj.strftime('%B %Y'),
        date_obj.strftime('%B')
    ]


def _coerce_search_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, (list, tuple, set)):
        return ', '.join(_coerce_search_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _normalise_entry_date(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.strptime(value, '%Y-%m-%d').strftime('%Y-%m-%d')
        except ValueError:
            return None
    return None


def _is_future_entry_date(value: str) -> bool:
    parsed = _parse_entry_date(value)
    if not parsed:
        return False

    today = datetime.now().date()
    return parsed.date() > today


def _normalise_entry_time(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(text, fmt).strftime('%H:%M')
        except ValueError:
            continue

    return None


def _normalise_update_field_value(field: str, value):
    if field == 'analysis_attachment_refs':
        if value is None or value == '':
            return '[]'
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return json.dumps([str(item) for item in value if str(item).strip()])
        return json.dumps([str(value)])
    return value


def _default_entry_time_for_kind(entry_kind: str) -> str:
    return '08:00' if entry_kind == 'dream' else '19:00'


def _build_daily_save_enrichment(
    *,
    title: str,
    user_message: str,
    user_tags: str,
    user_people: str,
    user_places: str,
) -> dict[str, str]:
    derived = derive_daily_nltk_fields(title, user_message)
    return {
        'tags': merge_csv_values(user_tags, derived.get('tags', '')),
        'daily_people_names': merge_csv_values(
            user_people,
            derived.get('daily_people_names', ''),
        ),
        'daily_places': merge_csv_values(
            user_places,
            derived.get('daily_places', ''),
        ),
    }


def _build_dream_save_enrichment(
    *,
    row_data: dict[str, str],
    user_tags: str,
    user_people: str,
    user_places: str,
) -> dict[str, str]:
    derived = derive_dream_nltk_fields(row_data)
    return {
        'tags': merge_csv_values(user_tags, derived.get('tags', '')),
        'dream_people_names': merge_csv_values(
            user_people,
            derived.get('dream_people_names', ''),
        ),
        'dream_places': merge_csv_values(
            user_places,
            derived.get('dream_places', ''),
        ),
    }


def _normalise_uploaded_entry_image(file_bytes: bytes) -> bytes:
    if not file_bytes:
        raise ValueError('No image data was uploaded.')

    try:
        image = Image.open(BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)
    except UnidentifiedImageError as exc:
        raise ValueError('The uploaded file is not a supported image.') from exc

    if image.mode not in ('RGB', 'L'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        alpha_source = image.convert('RGBA')
        background.paste(alpha_source, mask=alpha_source.split()[-1])
        image = background
    else:
        image = image.convert('RGB')

    resized = image.copy()
    resized.thumbnail(ENTRY_IMAGE_TARGET_SIZE, Image.Resampling.LANCZOS)

    output = BytesIO()
    resized.save(
        output,
        format='JPEG',
        quality=ENTRY_IMAGE_JPEG_QUALITY,
        optimize=True,
    )
    return output.getvalue()


def _normalise_image_position(value: object) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 50.0

    return max(0.0, min(100.0, numeric_value))


def _resolve_entry_image_value(
    conn: sqlite3.Connection,
    entry: dict,
    *,
    table_name: str,
    entry_kind: str,
    verify_media_exists: bool = True,
) -> dict:
    storage_key = str(entry.get('image_storage_key') or '').strip()
    image_value = entry.get('image_url')

    if storage_key:
        if not verify_media_exists or media_path_exists(storage_key):
            entry['image_url'] = resolve_image_url(storage_key)
        else:
            current_app.logger.warning('Entry image missing on disk for %s %s: %s', table_name, entry.get('id'), storage_key)
            entry['image_url'] = None
        entry.pop('image_storage_key', None)
        return entry

    if is_legacy_data_url(image_value):
        try:
            migrated_key = migrate_legacy_data_url(
                str(image_value),
                user_id=int(entry['user_id']),
                entry_kind=entry_kind,
            )
            conn.execute(
                f'UPDATE {table_name} SET image_storage_key = ?, image_url = NULL WHERE id = ? AND user_id = ?',
                (migrated_key, entry['id'], entry['user_id']),
            )
            entry['image_url'] = resolve_image_url(migrated_key)
            entry['image_storage_key'] = migrated_key
        except Exception as exc:
            current_app.logger.warning(
                'Legacy entry image migration skipped for %s %s: %s',
                table_name,
                entry.get('id'),
                exc,
            )

    if not entry.get('image_url'):
        entry['image_url'] = None

    image_source = str(entry.get('image_source') or '').strip().lower()
    if not image_source and entry.get('image_url'):
        image_source = 'ai' if str(entry.get('image_prompt') or '').strip() else 'upload'
        try:
            conn.execute(
                f'UPDATE {table_name} SET image_source = ? WHERE id = ? AND user_id = ?',
                (image_source, entry['id'], entry['user_id']),
            )
        except Exception:
            current_app.logger.warning(
                'Entry image source backfill skipped for %s %s',
                table_name,
                entry.get('id'),
            )

    entry['image_position_x'] = _normalise_image_position(entry.get('image_position_x'))
    entry['image_position_y'] = _normalise_image_position(entry.get('image_position_y'))
    entry['image_source'] = image_source or None
    entry.pop('image_storage_key', None)
    return entry


def _infer_daily_scene_category(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ('work', 'office', 'meeting', 'email', 'deadline')):
        return 'a work or responsibility-oriented moment'
    if any(token in lower for token in ('walk', 'park', 'outside', 'street', 'journey', 'drive', 'train')):
        return 'an outdoor or transitional everyday moment'
    if any(token in lower for token in ('bumble', 'whatsapp', 'message', 'texted', 'call', 'date')):
        return 'a private interpersonal or communication-focused moment'
    if any(token in lower for token in ('home', 'house', 'room', 'bed', 'kitchen')):
        return 'a quiet domestic moment'
    return 'an emotionally significant everyday moment'


def _infer_daily_emotional_tone(title: str, user_message: str, ai_response: str) -> str:
    lower = f'{title} {user_message} {ai_response}'.lower()
    if any(token in lower for token in ('anxious', 'uncertain', 'worried', 'nervous', 'uneasy')):
        return 'subtle uncertainty with emotional tension'
    if any(token in lower for token in ('sad', 'upset', 'hurt', 'grief', 'loss')):
        return 'tender sadness and emotional weight'
    if any(token in lower for token in ('happy', 'joy', 'excited', 'hopeful', 'relief')):
        return 'gentle hopefulness and emotional lift'
    if any(token in lower for token in ('angry', 'frustrated', 'resentful', 'irritated')):
        return 'contained frustration and internal pressure'
    return 'reflective emotional ambiguity'


def _infer_daily_symbolic_cue(title: str, user_message: str) -> str:
    lower = f'{title} {user_message}'.lower()
    if any(token in lower for token in ('phone', 'message', 'whatsapp', 'bumble', 'text')):
        return 'use symbolic communication cues without any readable screens'
    if any(token in lower for token in ('walk', 'road', 'street', 'path')):
        return 'use path or journey imagery to suggest emotional movement'
    if any(token in lower for token in ('dad', 'family', 'home')):
        return 'use intimate domestic details to suggest memory and emotional context'
    return 'use restrained environmental symbolism rather than literal storytelling'


def _derive_daily_image_prompt(entry: sqlite3.Row) -> str | None:
    title = str(entry['title'] or '').strip()
    user_message = str(entry['user_message'] or '').strip()
    ai_response = str(entry['ai_response'] or '').strip()

    if not user_message or not ai_response:
        return None

    scene_category = _infer_daily_scene_category(user_message)
    emotional_tone = _infer_daily_emotional_tone(title, user_message, ai_response)
    symbolic_cue = _infer_daily_symbolic_cue(title, user_message)

    prompt_parts = [
        'Create a single anonymous, visually grounded scene inspired by the emotional core of this diary entry.',
    ]
    if title:
        prompt_parts.append(f'Theme: {title[:120]}.')
    prompt_parts.append(f'Scene category: {scene_category}.')
    prompt_parts.append(f'Emotional tone: {emotional_tone}.')
    prompt_parts.append(f'Symbolic cue: {symbolic_cue}.')
    prompt_parts.append(
        'Focus on atmosphere, body language, setting, and one emotionally meaningful moment rather than a literal replay of events.'
    )
    prompt_parts.append('Show a single scene or symbolic composition, not a collage.')
    prompt_parts.append('Keep people anonymous and avoid legible devices or readable surfaces.')
    prompt_parts.append('Do not render any visible text, names, letters, numbers, chat messages, phone screens, app interfaces, signage, captions, or typography in the image.')
    return ' '.join(prompt_parts)


def _serialise_entry_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    table_name: str,
    entry_kind: str,
    include_import_metadata: bool = False,
    include_attachment_details: bool = True,
    attachment_summaries_by_id: dict[int, list[dict]] | None = None,
    verify_media_exists: bool = True,
) -> dict:
    entry = dict(row)
    if 'image_position_x' in entry or 'image_position_y' in entry:
        entry = _resolve_entry_image_value(
            conn,
            entry,
            table_name=table_name,
            entry_kind=entry_kind,
            verify_media_exists=verify_media_exists,
        )
    if entry.get('id') is not None and entry.get('user_id') is not None:
        entry['attachments'] = (
            _serialise_entry_assets(
                conn,
                user_id=int(entry['user_id']),
                entry_type=entry_kind,
                entry_id=int(entry['id']),
                verify_media_exists=verify_media_exists,
            )
            if include_attachment_details
            else (
                attachment_summaries_by_id.get(int(entry['id']), [])
                if attachment_summaries_by_id is not None
                else _serialise_entry_asset_summaries(
                    conn,
                    user_id=int(entry['user_id']),
                    entry_type=entry_kind,
                    entry_id=int(entry['id']),
                )
            )
        )
    entry['import_metadata'] = None
    if include_import_metadata and entry.get('import_id'):
        history_row = conn.execute(
            '''SELECT imported_at, filename
               FROM import_history
               WHERE id = ? AND user_id = ?''',
            (entry['import_id'], entry['user_id']),
        ).fetchone()
        if history_row:
            entry['import_metadata'] = dict(history_row)
    return entry


def _load_entry_asset_summary_map(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    entry_type: str,
) -> dict[int, list[dict]]:
    rows = conn.execute(
        '''
        SELECT entry_id, id, mime_type
        FROM entry_assets
        WHERE user_id = ? AND entry_type = ?
        ORDER BY sort_order ASC, id ASC
        ''',
        (user_id, entry_type),
    ).fetchall()
    summaries: dict[int, list[dict]] = {}
    for row in rows:
        entry_id = int(row['entry_id'])
        summaries.setdefault(entry_id, []).append(
            {
                'id': row['id'],
                'mime_type': str(row['mime_type'] or '').strip().lower(),
            }
        )
    return summaries


def _serialise_entry_asset_summaries(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    entry_type: str,
    entry_id: int,
) -> list[dict]:
    rows = conn.execute(
        '''
        SELECT id, mime_type
        FROM entry_assets
        WHERE user_id = ? AND entry_type = ? AND entry_id = ?
        ORDER BY sort_order ASC, id ASC
        ''',
        (user_id, entry_type, entry_id),
    ).fetchall()
    return [
        {
            'id': row['id'],
            'mime_type': str(row['mime_type'] or '').strip().lower(),
        }
        for row in rows
    ]


def _serialise_entry_assets(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    entry_type: str,
    entry_id: int,
    verify_media_exists: bool = True,
) -> list[dict]:
    rows = conn.execute(
        '''
        SELECT id, asset_role, storage_key, original_filename, mime_type,
               file_size_bytes, sort_order, created_at,
               derived_text, derived_text_source, derived_text_updated_at
        FROM entry_assets
        WHERE user_id = ? AND entry_type = ? AND entry_id = ?
        ORDER BY sort_order ASC, id ASC
        ''',
        (user_id, entry_type, entry_id),
    ).fetchall()

    attachments: list[dict] = []
    for row in rows:
        storage_key = str(row['storage_key'] or '').strip()
        if not storage_key:
            continue
        if verify_media_exists and not media_path_exists(storage_key):
            current_app.logger.warning(
                'Entry attachment missing on disk for %s %s asset %s: %s',
                entry_type,
                entry_id,
                row['id'],
                storage_key,
            )
            continue

        mime_type = str(row['mime_type'] or '').strip().lower()
        attachments.append(
            {
                'id': row['id'],
                'asset_role': row['asset_role'],
                'original_filename': row['original_filename'],
                'mime_type': mime_type,
                'file_size_bytes': int(row['file_size_bytes'] or 0),
                'sort_order': int(row['sort_order'] or 0),
                'created_at': row['created_at'],
                'derived_text': str(row['derived_text'] or ''),
                'derived_text_source': str(row['derived_text_source'] or ''),
                'derived_text_updated_at': row['derived_text_updated_at'],
                'has_derived_text': bool(str(row['derived_text'] or '').strip()),
                'url': resolve_image_url(storage_key),
                'is_image': mime_type.startswith('image/'),
                'is_audio': mime_type.startswith('audio/'),
                'is_pdf': mime_type == 'application/pdf',
            }
        )

    return attachments


def _delete_entry_assets(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    entry_type: str,
    entry_id: int,
) -> list[str]:
    rows = conn.execute(
        '''
        SELECT storage_key
        FROM entry_assets
        WHERE user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (user_id, entry_type, entry_id),
    ).fetchall()
    conn.execute(
        '''
        DELETE FROM entry_assets
        WHERE user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (user_id, entry_type, entry_id),
    )
    return [str(row['storage_key'] or '').strip() for row in rows if row['storage_key']]


def _unlink_cbt_worksheets(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    entry_type: str | None = None,
    entry_id: int | None = None,
) -> None:
    """Preserve reflections while removing links to entries being deleted."""
    try:
        if entry_type is None or entry_id is None:
            conn.execute(
                '''
                UPDATE cbt_worksheets
                SET linked_entry_type = NULL, linked_entry_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND linked_entry_id IS NOT NULL
                ''',
                (user_id,),
            )
            return
        conn.execute(
            '''
            UPDATE cbt_worksheets
            SET linked_entry_type = NULL, linked_entry_id = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND linked_entry_type = ? AND linked_entry_id = ?
            ''',
            (user_id, entry_type, entry_id),
        )
    except sqlite3.OperationalError as exc:
        if 'no such table' not in str(exc).lower():
            raise


def _get_attachment_limit_for_mime_type(mime_type: str) -> int:
    if mime_type.startswith('audio/'):
        return MAX_ENTRY_AUDIO_ATTACHMENT_BYTES
    return MAX_ENTRY_IMAGE_OR_PDF_ATTACHMENT_BYTES


def _upload_entry_attachment(
    *,
    table_name: str,
    entry_type: str,
    entry_id: int,
    user_id: int,
) -> tuple[dict, int]:
    if 'attachment' not in request.files:
        return {'error': 'Upload a file using the "attachment" field.'}, 400

    uploaded_file = request.files['attachment']
    if not uploaded_file or not uploaded_file.filename:
        return {'error': 'No attachment file was selected.'}, 400

    content_type = (uploaded_file.content_type or '').lower().strip()
    if content_type not in ALLOWED_ENTRY_ATTACHMENT_MIME_TYPES:
        return {
            'error': 'Unsupported attachment type. Use PDF, JPG, PNG, WEBP, MP3, WAV, M4A, OGG, WEBM, or AIFF.'
        }, 400

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return {'error': 'The selected attachment file is empty.'}, 400
    if len(file_bytes) > MAX_ENTRY_ATTACHMENT_UPLOAD_BYTES:
        return {'error': 'Attachment files must be 15 MB or smaller.'}, 400

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        f'SELECT id FROM {table_name} WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()
    if not entry:
        conn.close()
        return {'error': 'Entry not found'}, 404

    existing_count = cursor.execute(
        '''
        SELECT COUNT(*) AS asset_count
        FROM entry_assets
        WHERE user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (user_id, entry_type, entry_id),
    ).fetchone()
    if int(existing_count['asset_count'] or 0) >= MAX_ATTACHMENTS_PER_ENTRY:
        conn.close()
        return {
            'error': f'Each entry can have up to {MAX_ATTACHMENTS_PER_ENTRY} attachments.'
        }, 400

    size_limit = _get_attachment_limit_for_mime_type(content_type)
    if len(file_bytes) > size_limit:
        conn.close()
        size_limit_mb = int(size_limit / (1024 * 1024))
        file_group = 'Audio files' if content_type.startswith('audio/') else 'Image and PDF files'
        return {'error': f'{file_group} must be {size_limit_mb} MB or smaller.'}, 400

    try:
        enforce_storage_limit(conn, user_id=user_id, incoming_bytes=len(file_bytes))
    except UsageLimitExceeded as exc:
        conn.close()
        return _quota_exceeded_payload(
            exc,
            'This plan has reached its media storage limit. Delete media or upgrade from Account.',
        )
    except Exception:
        current_app.logger.exception('Storage usage check failed for %s attachment upload', entry_type)
        conn.close()
        return {'error': 'Storage usage could not be checked. Please try again.'}, 503

    try:
        storage_key = store_entry_asset(
            file_bytes,
            user_id=user_id,
            entry_kind=entry_type,
            filename=uploaded_file.filename,
        )
    except ValueError as exc:
        conn.close()
        return {'error': str(exc)}, 400

    derived_text = None
    derived_text_source = None
    derived_text_updated_at = None
    if content_type == 'application/pdf':
        try:
            extracted_text, extracted_text_source = extract_pdf_attachment_content(file_bytes)
            if extracted_text:
                if extracted_text_source == 'pdf-ocr':
                    try:
                        extracted_text = OpenAIService().clean_ocr_extracted_text(extracted_text)
                    except AnalysisRateLimitError:
                        current_app.logger.warning(
                            'PDF OCR cleanup rate-limited for uploaded %s attachment "%s"; using raw OCR text.',
                            entry_type,
                            uploaded_file.filename,
                        )
                    except Exception:
                        current_app.logger.exception(
                            'PDF OCR cleanup failed for uploaded %s attachment "%s"; using raw OCR text.',
                            entry_type,
                            uploaded_file.filename,
                        )
                derived_text = extracted_text
                derived_text_source = extracted_text_source or 'pdf-text-extraction'
                derived_text_updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            current_app.logger.exception(
                'PDF text extraction failed for uploaded %s attachment "%s"',
                entry_type,
                uploaded_file.filename,
            )

    cursor.execute(
        append_returning_id(
            '''
        INSERT INTO entry_assets
        (user_id, entry_type, entry_id, asset_role, storage_key, original_filename, mime_type, file_size_bytes,
         derived_text, derived_text_source, derived_text_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
            _database_provider(),
        ),
        (
            user_id,
            entry_type,
            entry_id,
            'attachment',
            storage_key,
            uploaded_file.filename,
            content_type,
            len(file_bytes),
            derived_text,
            derived_text_source,
            derived_text_updated_at,
        ),
    )
    asset_id = inserted_id(cursor, _database_provider())
    conn.commit()
    attachment = _serialise_entry_assets(
        conn,
        user_id=user_id,
        entry_type=entry_type,
        entry_id=entry_id,
    )
    conn.close()

    created = next((item for item in attachment if item['id'] == asset_id), None)
    return {
        'entry_id': entry_id,
        'entry_type': entry_type,
        'attachment': created,
    }, 201


def _delete_entry_attachment(
    *,
    entry_type: str,
    table_name: str,
    entry_id: int,
    asset_id: int,
    user_id: int,
) -> tuple[dict, int]:
    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        f'SELECT id FROM {table_name} WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()
    if not entry:
        conn.close()
        return {'error': 'Entry not found'}, 404

    asset = cursor.execute(
        '''
        SELECT id, storage_key
        FROM entry_assets
        WHERE id = ? AND user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (asset_id, user_id, entry_type, entry_id),
    ).fetchone()
    if not asset:
        conn.close()
        return {'error': 'Attachment not found'}, 404

    cursor.execute(
        'DELETE FROM entry_assets WHERE id = ? AND user_id = ?',
        (asset_id, user_id),
    )
    conn.commit()
    conn.close()

    delete_image(asset['storage_key'])

    return {
        'entry_id': entry_id,
        'entry_type': entry_type,
        'deleted_attachment_id': asset_id,
    }, 200


def _download_entry_attachment(
    *,
    entry_type: str,
    table_name: str,
    entry_id: int,
    asset_id: int,
    user_id: int,
):
    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        f'SELECT id FROM {table_name} WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    asset = cursor.execute(
        '''
        SELECT storage_key, original_filename, mime_type
        FROM entry_assets
        WHERE id = ? AND user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (asset_id, user_id, entry_type, entry_id),
    ).fetchone()
    conn.close()
    if not asset:
        return jsonify({'error': 'Attachment not found'}), 404

    file_bytes = read_image_bytes(asset['storage_key'])
    if file_bytes is None:
        return jsonify({'error': 'Attachment file is missing.'}), 404

    return send_file(
        BytesIO(file_bytes),
        mimetype=str(asset['mime_type'] or 'application/octet-stream'),
        as_attachment=True,
        download_name=str(asset['original_filename'] or f'attachment-{asset_id}'),
    )


def _transcribe_entry_attachment(
    *,
    entry_type: str,
    table_name: str,
    entry_id: int,
    asset_id: int,
    user_id: int,
) -> tuple[dict, int]:
    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        f'SELECT id FROM {table_name} WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()
    if not entry:
        conn.close()
        return {'error': 'Entry not found'}, 404

    asset = cursor.execute(
        '''
        SELECT id, storage_key, original_filename, mime_type
        FROM entry_assets
        WHERE id = ? AND user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (asset_id, user_id, entry_type, entry_id),
    ).fetchone()
    if not asset:
        conn.close()
        return {'error': 'Attachment not found'}, 404

    mime_type = str(asset['mime_type'] or '').strip().lower()
    if not mime_type.startswith('audio/'):
        conn.close()
        return {'error': 'Only audio attachments can be transcribed.'}, 400

    file_bytes = read_image_bytes(asset['storage_key'])
    if file_bytes is None:
        conn.close()
        return {'error': 'Attachment file is missing.'}, 404

    quota_error = _check_usage_or_error(
        conn,
        user_id=user_id,
        event_type=TRANSCRIPTION_MINUTE_EVENT,
        units=1,
        message='This plan has reached its monthly audio transcription limit.',
    )
    if quota_error:
        conn.close()
        return quota_error

    try:
        transcript_text = OpenAIService().transcribe_audio_attachment(
            file_bytes,
            filename=str(asset['original_filename'] or f'attachment-{asset_id}'),
            mime_type=mime_type,
        )
    except AnalysisRateLimitError:
        conn.close()
        return {'error': 'Audio transcription is temporarily rate-limited. Please try again later.'}, 429
    except ValueError as exc:
        conn.close()
        return {'error': str(exc)}, 400
    except Exception:
        conn.close()
        current_app.logger.exception('Attachment transcription failed for %s attachment %s', entry_type, asset_id)
        return {'error': 'Audio transcription failed.'}, 502

    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cursor.execute(
        '''
        UPDATE entry_assets
        SET derived_text = ?, derived_text_source = ?, derived_text_updated_at = ?
        WHERE id = ? AND user_id = ?
        ''',
        (transcript_text, 'audio-transcription', updated_at, asset_id, user_id),
    )
    _record_usage_safely(
        conn,
        user_id=user_id,
        event_type=TRANSCRIPTION_MINUTE_EVENT,
        units=1,
        metadata={'entry_type': entry_type, 'asset_id': asset_id},
    )
    conn.commit()
    attachments = _serialise_entry_assets(
        conn,
        user_id=user_id,
        entry_type=entry_type,
        entry_id=entry_id,
    )
    conn.close()

    updated_attachment = next((item for item in attachments if item['id'] == asset_id), None)
    return {
        'entry_id': entry_id,
        'entry_type': entry_type,
        'attachment': updated_attachment,
    }, 200


def _derive_pdf_attachment_text(
    *,
    entry_type: str,
    table_name: str,
    entry_id: int,
    asset_id: int,
    user_id: int,
    force_refresh: bool = True,
) -> tuple[dict, int]:
    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        f'SELECT id FROM {table_name} WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()
    if not entry:
        conn.close()
        return {'error': 'Entry not found'}, 404

    asset = cursor.execute(
        '''
        SELECT id, storage_key, original_filename, mime_type, derived_text, derived_text_source
        FROM entry_assets
        WHERE id = ? AND user_id = ? AND entry_type = ? AND entry_id = ?
        ''',
        (asset_id, user_id, entry_type, entry_id),
    ).fetchone()
    if not asset:
        conn.close()
        return {'error': 'Attachment not found'}, 404

    mime_type = str(asset['mime_type'] or '').strip().lower()
    if mime_type != 'application/pdf':
        conn.close()
        return {'error': 'Only PDF attachments can derive text.'}, 400

    existing_text = str(asset['derived_text'] or '').strip()
    existing_source = str(asset['derived_text_source'] or '').strip()
    if existing_text and not force_refresh and not (
        existing_source == 'pdf-ocr' and looks_like_low_quality_ocr_text(existing_text)
    ):
        attachments = _serialise_entry_assets(
            conn,
            user_id=user_id,
            entry_type=entry_type,
            entry_id=entry_id,
        )
        conn.close()
        updated_attachment = next((item for item in attachments if item['id'] == asset_id), None)
        return {
            'entry_id': entry_id,
            'entry_type': entry_type,
            'attachment': updated_attachment,
        }, 200

    file_bytes = read_image_bytes(asset['storage_key'])
    if file_bytes is None:
        conn.close()
        return {'error': 'Attachment file is missing.'}, 404

    try:
        extracted_text, extracted_text_source = extract_pdf_attachment_content(file_bytes)
        if not extracted_text:
            conn.close()
            return {'error': 'No extractable PDF text was found.'}, 422
        if extracted_text_source == 'pdf-ocr':
            quota_error = _check_usage_or_error(
                conn,
                user_id=user_id,
                event_type=OCR_PAGE_EVENT,
                units=1,
                message='This plan has reached its monthly OCR limit.',
            )
            if quota_error:
                conn.close()
                return quota_error
            extracted_text = OpenAIService().clean_ocr_extracted_text(extracted_text)
    except AnalysisRateLimitError:
        conn.close()
        return {'error': 'PDF text cleanup is temporarily rate-limited. Please try again later.'}, 429
    except ValueError as exc:
        conn.close()
        return {'error': str(exc)}, 400
    except Exception:
        conn.close()
        current_app.logger.exception('PDF text extraction failed for %s attachment %s', entry_type, asset_id)
        return {'error': 'PDF text extraction failed.'}, 502

    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    cursor.execute(
        '''
        UPDATE entry_assets
        SET derived_text = ?, derived_text_source = ?, derived_text_updated_at = ?
        WHERE id = ? AND user_id = ?
        ''',
        (
            extracted_text,
            extracted_text_source or 'pdf-text-extraction',
            updated_at,
            asset_id,
            user_id,
        ),
    )
    if extracted_text_source == 'pdf-ocr':
        _record_usage_safely(
            conn,
            user_id=user_id,
            event_type=OCR_PAGE_EVENT,
            units=1,
            metadata={'entry_type': entry_type, 'asset_id': asset_id},
        )
    conn.commit()
    attachments = _serialise_entry_assets(
        conn,
        user_id=user_id,
        entry_type=entry_type,
        entry_id=entry_id,
    )
    conn.close()

    updated_attachment = next((item for item in attachments if item['id'] == asset_id), None)
    return {
        'entry_id': entry_id,
        'entry_type': entry_type,
        'attachment': updated_attachment,
    }, 200


def _get_entry_range_summary(conn: sqlite3.Connection, user_id: int) -> dict[str, int | str | None | bool]:
    daily_row = conn.execute(
        'SELECT MIN(entry_date) AS min_date, MAX(entry_date) AS max_date, COUNT(*) AS total_count FROM dailydiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    dream_row = conn.execute(
        'SELECT MIN(entry_date) AS min_date, MAX(entry_date) AS max_date, COUNT(*) AS total_count FROM dreamdiary_entries WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    important_day_row = conn.execute(
        'SELECT MIN(starts_on) AS min_date, MAX(starts_on) AS max_date, COUNT(*) AS total_count FROM important_days WHERE user_id = ?',
        (user_id,),
    ).fetchone()
    thought_record_row = conn.execute(
        'SELECT MIN(record_date) AS min_date, MAX(record_date) AS max_date, COUNT(*) AS total_count FROM cbt_worksheets WHERE user_id = ?',
        (user_id,),
    ).fetchone()

    all_min_dates = [
        value
        for value in [
            daily_row['min_date'],
            dream_row['min_date'],
            important_day_row['min_date'],
            thought_record_row['min_date'],
        ]
        if value
    ]
    all_max_dates = [
        value
        for value in [
            daily_row['max_date'],
            dream_row['max_date'],
            important_day_row['max_date'],
            thought_record_row['max_date'],
        ]
        if value
    ]
    daily_count = int(daily_row['total_count'] or 0)
    dream_count = int(dream_row['total_count'] or 0)
    important_day_count = int(important_day_row['total_count'] or 0)
    thought_record_count = int(thought_record_row['total_count'] or 0)
    total_count = daily_count + dream_count + important_day_count + thought_record_count

    return {
        'first_entry_date': min(all_min_dates) if all_min_dates else None,
        'last_entry_date': max(all_max_dates) if all_max_dates else None,
        'daily_count': daily_count,
        'dream_count': dream_count,
        'important_day_count': important_day_count,
        'thought_record_count': thought_record_count,
        'total_entries': total_count,
        'has_entries': total_count > 0,
    }


def _build_bulk_delete_readiness(
    conn: sqlite3.Connection,
    user_id: int,
    guard_token: str | None,
) -> dict[str, int | str | None | bool]:
    ensure_export_history_table(conn)
    summary = _get_entry_range_summary(conn, user_id)
    guard_record = get_latest_bulk_delete_guard(conn, user_id, guard_token)

    guard_covers_full_range = bool(
        guard_record
        and guard_record.get('is_full_range')
        and guard_record.get('include_daily') == 1
        and guard_record.get('include_dreams') == 1
        and (
            (
                guard_record.get('from_date') == summary['first_entry_date']
                and guard_record.get('to_date') == summary['last_entry_date']
            )
            or (
                guard_record.get('from_date') is None
                and guard_record.get('to_date') is None
            )
        )
    )
    eligible = bool(summary['has_entries'] and guard_covers_full_range)

    return {
        **summary,
        'eligible_for_delete': eligible,
        'guard_token_present': bool(guard_record),
        'requires_full_export': bool(summary['has_entries']),
    }


def _build_search_pattern(term: str, *, phrase: bool = False) -> re.Pattern:
    if phrase or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", term, re.IGNORECASE):
        return re.compile(re.escape(term), re.IGNORECASE)
    return re.compile(rf'(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])', re.IGNORECASE)


def _search_term_matches(source: str, term: str, *, phrase: bool = False) -> bool:
    source = _coerce_search_text(source)
    if not source or not term:
        return False
    return bool(_build_search_pattern(term, phrase=phrase).search(source))


def _parse_search_query(query: str) -> dict:
    quoted_tokens = [
        token.strip()
        for token in re.findall(r'"([^"]+)"', query)
        if token.strip()
    ]
    if quoted_tokens and query.strip().startswith('"') and query.strip().endswith('"'):
        return {
            'mode': 'phrase',
            'terms': [{'text': token.lower(), 'phrase': True} for token in quoted_tokens],
            'phrase_text': quoted_tokens[0].lower(),
        }

    has_comma = ',' in query
    if has_comma:
        raw_terms = [token.strip() for token in re.split(r',+', query) if token.strip()]
    else:
        raw_terms = [
            token.strip('"')
            for token in re.findall(r'"[^"]+"|\S+', query)
            if token.strip('"').strip()
        ]

    terms = [
        {
            'text': token.lower(),
            'phrase': ' ' in token,
        }
        for token in raw_terms
        if token
    ]
    return {
        'mode': 'or' if has_comma else 'and',
        'terms': terms,
        'phrase_text': ' '.join(term['text'] for term in terms).strip() if not has_comma else '',
    }


def _find_search_matches(source: str, query_terms: list[dict]) -> list[tuple[int, int]]:
    matches: list[tuple[int, int]] = []
    for term in query_terms:
        text = str(term.get('text') or '')
        if not text:
            continue
        pattern = _build_search_pattern(text, phrase=bool(term.get('phrase')))
        matches.extend((match.start(), match.end()) for match in pattern.finditer(source))

    selected: list[tuple[int, int]] = []
    last_end = -1
    for start, end in sorted(matches, key=lambda item: (item[0], -(item[1] - item[0]))):
        if start < last_end:
            continue
        selected.append((start, end))
        last_end = end
    return selected


def _render_highlighted_search_excerpt(excerpt: str, query_terms: list[dict]) -> str:
    matches = _find_search_matches(excerpt, query_terms)
    if not matches:
        return escape(excerpt)

    parts: list[str] = []
    cursor = 0
    for start, end in matches:
        parts.append(escape(excerpt[cursor:start]))
        parts.append(
            '<span style="color: red; font-weight: bold;">'
            f'{escape(excerpt[start:end])}'
            '</span>'
        )
        cursor = end
    parts.append(escape(excerpt[cursor:]))
    return ''.join(parts)


def _highlight_text_terms(source: str, query_terms: list[dict], context: int = 60) -> str | None:
    source = _coerce_search_text(source)
    if not source:
        return None
    matches = _find_search_matches(source, query_terms)
    if not matches:
        return None

    first_start, first_end = matches[0]
    start = max(first_start - context, 0)
    end = min(first_end + context, len(source))
    excerpt = source[start:end]
    highlighted = _render_highlighted_search_excerpt(excerpt, query_terms)
    if start > 0:
        highlighted = '…' + highlighted
    if end < len(source):
        highlighted = highlighted + '…'
    return highlighted


def _highlight_inline_terms(source: str, query_terms: list[dict], max_length: int = 80) -> str | None:
    source = _coerce_search_text(source)
    if not source:
        return None
    matches = _find_search_matches(source, query_terms)
    if not matches:
        return None

    if len(source) <= max_length:
        return _render_highlighted_search_excerpt(source, query_terms)

    first_start, first_end = matches[0]
    context = max((max_length - (first_end - first_start)) // 2, 0)
    start = max(first_start - context, 0)
    end = min(first_end + context, len(source))

    if start > 0:
        space_before = source.rfind(' ', 0, start + 10)
        if space_before > start - 10:
            start = space_before + 1

    if end < len(source):
        space_after = source.find(' ', end - 10)
        if space_after != -1 and space_after < end + 10:
            end = space_after

    excerpt = source[start:end]
    highlighted = _render_highlighted_search_excerpt(excerpt, query_terms)
    if start > 0:
        highlighted = '…' + highlighted
    if end < len(source):
        highlighted = highlighted + '…'
    return highlighted


def _highlight_text(source: str, term: str, context: int = 60, *, phrase: bool = False) -> str | None:
    return _highlight_text_terms(
        source,
        [{'text': term, 'phrase': phrase}],
        context=context,
    )


def _highlight_inline(source: str, term: str, max_length: int = 80, *, phrase: bool = False) -> str | None:
    return _highlight_inline_terms(
        source,
        [{'text': term, 'phrase': phrase}],
        max_length=max_length,
    )

# Combined entries overview endpoint
@entries_bp.route('/entries/overview', methods=['GET'])
@jwt_required()
def get_entries_overview():
    """Return the primary data needed by the Entries cards/calendar view."""
    user_id = int(get_jwt_identity())

    conn = get_db()
    try:
        daily_rows = conn.execute(_sql('''
            SELECT * FROM dailydiary_entries
            WHERE user_id = ?
            ORDER BY entry_date DESC, COALESCE(entry_time, '19:00') DESC, entry_number DESC
        '''), (user_id,)).fetchall()
        dream_rows = conn.execute(_sql('''
            SELECT * FROM dreamdiary_entries
            WHERE user_id = ?
            ORDER BY entry_date DESC, COALESCE(entry_time, '08:00') DESC, entry_number DESC
        '''), (user_id,)).fetchall()
        thought_record_rows = conn.execute(
            _sql(
                _worksheet_query('w.user_id = ?') +
                ' ORDER BY w.updated_at DESC, w.id DESC'
            ),
            (user_id,),
        ).fetchall()
        important_day_rows = conn.execute(
            _sql(f'''
            {IMPORTANT_DAY_SELECT}
            WHERE user_id = ?
            ORDER BY month ASC, day ASC, lower(label) ASC, id ASC
            '''),
            (user_id,),
        ).fetchall()

        daily_attachment_summaries = _load_entry_asset_summary_map(
            conn,
            user_id=user_id,
            entry_type='daily',
        )
        dream_attachment_summaries = _load_entry_asset_summary_map(
            conn,
            user_id=user_id,
            entry_type='dream',
        )

        payload = {
            'daily': [
                _serialise_entry_row(
                    conn,
                    row,
                    table_name='dailydiary_entries',
                    entry_kind='daily',
                    include_attachment_details=False,
                    attachment_summaries_by_id=daily_attachment_summaries,
                    verify_media_exists=False,
                )
                for row in daily_rows
            ],
            'dreams': [
                _serialise_entry_row(
                    conn,
                    row,
                    table_name='dreamdiary_entries',
                    entry_kind='dream',
                    include_attachment_details=False,
                    attachment_summaries_by_id=dream_attachment_summaries,
                    verify_media_exists=False,
                )
                for row in dream_rows
            ],
            'thought_records': [
                _serialise_worksheet(row)
                for row in thought_record_rows
            ],
            'important_days': [
                _serialise_important_day(row)
                for row in important_day_rows
            ],
        }
        conn.commit()
        return jsonify(payload), 200
    finally:
        conn.close()


# Daily entries endpoints
@entries_bp.route('/daily', methods=['GET'])
@jwt_required()
def get_daily_entries():
    """Get all daily entries for authenticated user."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entries = cursor.execute('''
        SELECT * FROM dailydiary_entries
        WHERE user_id = ?
        ORDER BY entry_date DESC, COALESCE(entry_time, '19:00') DESC, entry_number DESC
    ''', (user_id,)).fetchall()
    attachment_summaries_by_id = _load_entry_asset_summary_map(
        conn,
        user_id=user_id,
        entry_type='daily',
    )
    
    payload = [
        _serialise_entry_row(
            conn,
            entry,
            table_name='dailydiary_entries',
            entry_kind='daily',
            include_attachment_details=False,
            attachment_summaries_by_id=attachment_summaries_by_id,
            verify_media_exists=False,
        )
        for entry in entries
    ]
    conn.commit()
    conn.close()
    
    return jsonify(payload), 200

@entries_bp.route('/daily/<int:entry_id>', methods=['GET'])
@jwt_required()
def get_daily_entry(entry_id):
    """Get specific daily entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entry = cursor.execute('''
        SELECT * FROM dailydiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id)).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    payload = _serialise_entry_row(
        conn,
        entry,
        table_name='dailydiary_entries',
        entry_kind='daily',
        include_import_metadata=True,
    )
    conn.commit()
    conn.close()
    
    return jsonify(payload), 200

@entries_bp.route('/daily', methods=['POST'])
@jwt_required()
def create_daily_entry():
    """Create new daily entry."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    entry_date = _normalise_entry_date(
        data.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
    )
    entry_time = _normalise_entry_time(
        data.get('entry_time', datetime.now().strftime('%H:%M'))
    )
    if not entry_date:
        return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
    if not entry_time:
        return jsonify({'error': 'Invalid entry_time format. Use HH:MM'}), 400
    if _is_future_entry_date(entry_date):
        return jsonify({'error': 'Future entry dates are not allowed'}), 400

    user_message = data.get('user_message', '')
    title = data.get('title', '')
    enrichment = _build_daily_save_enrichment(
        title=title,
        user_message=user_message,
        user_tags=data.get('tags', ''),
        user_people=data.get('daily_people_names', ''),
        user_places=data.get('daily_places', ''),
    )
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get next entry number for the day
    max_entry = cursor.execute('''
        SELECT MAX(entry_number) as max_num
        FROM dailydiary_entries
        WHERE user_id = ? AND entry_date = ?
    ''', (user_id, entry_date)).fetchone()
    
    entry_number = (max_entry['max_num'] or 0) + 1
    
    cursor.execute(append_returning_id('''
        INSERT INTO dailydiary_entries 
        (user_id, entry_date, entry_time, entry_number, title, user_message, tags, mood, ai_style, daily_people_names, daily_places)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', _database_provider()), (
        user_id,
        entry_date,
        entry_time,
        entry_number,
        title,
        user_message,
        enrichment['tags'],
        data.get('mood', ''),
        data.get('ai_style', ''),
        enrichment['daily_people_names'],
        enrichment['daily_places'],
    ))
    
    entry_id = inserted_id(cursor, _database_provider())
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': entry_id,
        'entry_date': entry_date,
        'entry_time': entry_time,
        'entry_number': entry_number,
        'title': title
    }), 201

@entries_bp.route('/daily/<int:entry_id>', methods=['PUT'])
@jwt_required()
def update_daily_entry(entry_id):
    """Update daily entry with AI analysis results."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check ownership
    entry = cursor.execute(
        '''SELECT id, entry_date, title, user_message, tags, daily_people_names, daily_places
           FROM dailydiary_entries WHERE id = ? AND user_id = ?''',
        (entry_id, user_id)
    ).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404
    
    # Update allowed fields
    allowed_fields = [
        'title', 'user_message', 'ai_response',
        'mood', 'ai_style', 'image_prompt', 'recycled_image_prompt',
        'image_url', 'image_position_x', 'image_position_y', 'analysis_attachment_refs'
    ]
    updates = []
    values = []

    if 'entry_date' in data:
        parsed_entry_date = _normalise_entry_date(data.get('entry_date'))
        if not parsed_entry_date:
            conn.close()
            return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
        if _is_future_entry_date(parsed_entry_date):
            conn.close()
            return jsonify({'error': 'Future entry dates are not allowed'}), 400

        updates.append('entry_date = ?')
        values.append(parsed_entry_date)

        if parsed_entry_date != entry['entry_date']:
            max_entry = cursor.execute('''
                SELECT MAX(entry_number) as max_num
                FROM dailydiary_entries
                WHERE user_id = ? AND entry_date = ?
            ''', (user_id, parsed_entry_date)).fetchone()
            entry_number = (max_entry['max_num'] or 0) + 1
            updates.append('entry_number = ?')
            values.append(entry_number)

    if 'entry_time' in data:
        parsed_entry_time = _normalise_entry_time(data.get('entry_time'))
        if not parsed_entry_time:
            conn.close()
            return jsonify({'error': 'Invalid entry_time format. Use HH:MM'}), 400
        updates.append('entry_time = ?')
        values.append(parsed_entry_time)
    
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(_normalise_update_field_value(field, data[field]))

    effective_title = data.get('title', entry['title'])
    effective_user_message = data.get('user_message', entry['user_message'])
    effective_tags = data.get('tags', entry['tags'])
    effective_people = data.get('daily_people_names', entry['daily_people_names'])
    effective_places = data.get('daily_places', entry['daily_places'])
    enrichment = _build_daily_save_enrichment(
        title=effective_title,
        user_message=effective_user_message,
        user_tags=effective_tags,
        user_people=effective_people,
        user_places=effective_places,
    )
    updates.extend([
        'tags = ?',
        'daily_people_names = ?',
        'daily_places = ?',
    ])
    values.extend([
        enrichment['tags'],
        enrichment['daily_people_names'],
        enrichment['daily_places'],
    ])
    
    if not updates:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(entry_id)
    values.append(user_id)
    
    cursor.execute(f'''
        UPDATE dailydiary_entries
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
    ''', values)
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Entry updated'}), 200

@entries_bp.route('/daily/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_daily_entry(entry_id):
    """Delete daily entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        'SELECT image_storage_key FROM dailydiary_entries WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    attachment_keys = _delete_entry_assets(
        conn,
        user_id=user_id,
        entry_type='daily',
        entry_id=entry_id,
    )
    _unlink_cbt_worksheets(
        conn,
        user_id=user_id,
        entry_type='daily',
        entry_id=entry_id,
    )

    cursor.execute('''
        DELETE FROM dailydiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id))
    
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({'error': 'Entry not found'}), 404

    delete_image(entry['image_storage_key'])
    for storage_key in attachment_keys:
        delete_image(storage_key)
    
    return '', 204


@entries_bp.route('/daily/<int:entry_id>/generate-image', methods=['POST'])
@jwt_required()
def generate_daily_image(entry_id):
    """Generate or regenerate a daily image from stored, derived, or overridden prompt."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, title, user_message, ai_response, image_prompt, image_url,
                  image_storage_key, recycled_image_prompt, image_position_x, image_position_y, image_source
           FROM dailydiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    image_prompt_override = (data.get('image_prompt_override') or '').strip()
    stored_prompt = (entry['image_prompt'] or '').strip()
    derived_prompt = _derive_daily_image_prompt(entry) if not stored_prompt and not image_prompt_override else None
    image_prompt = image_prompt_override or stored_prompt or (derived_prompt or '').strip()

    if not image_prompt:
        conn.close()
        return jsonify({'error': 'This daily entry needs saved AI analysis before an image can be generated.'}), 400

    quota_error = _check_usage_or_error(
        conn,
        user_id=user_id,
        event_type=AI_IMAGE_EVENT,
        units=1,
        message='This plan has reached its monthly AI image limit.',
    )
    if quota_error:
        conn.close()
        payload, status_code = quota_error
        return jsonify(payload), status_code

    try:
        ai_service = OpenAIService()
        image_bytes = ai_service.generate_image(
            image_prompt,
            style_prefix=os.getenv('OPENAI_DAILY_IMAGE_STYLE_PREFIX', DAILY_IMAGE_STYLE_PREFIX),
        )
        storage_key = store_generated_image(
            image_bytes,
            user_id=user_id,
            entry_kind='daily',
        )
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 503
    except Exception as exc:
        current_app.logger.error('Daily image generation failed for entry %s: %s', entry_id, exc)
        conn.close()
        return jsonify({'error': 'Image generation failed'}), 502

    if image_prompt_override:
        cursor.execute(
            'UPDATE dailydiary_entries SET image_storage_key = ?, image_url = NULL, image_source = ? WHERE id = ? AND user_id = ?',
            (storage_key, 'ai', entry_id, user_id),
        )
    else:
        cursor.execute(
            'UPDATE dailydiary_entries SET image_storage_key = ?, image_url = NULL, image_prompt = ?, image_source = ? WHERE id = ? AND user_id = ?',
            (storage_key, image_prompt, 'ai', entry_id, user_id),
        )
    _record_usage_safely(
        conn,
        user_id=user_id,
        event_type=AI_IMAGE_EVENT,
        metadata={'entry_type': 'daily', 'entry_id': entry_id},
    )
    conn.commit()
    conn.close()
    delete_image(entry['image_storage_key'])

    return jsonify({
        'id': entry_id,
        'image_prompt': image_prompt,
        'image_url': resolve_image_url(storage_key),
        'has_existing_image': bool(entry['image_url'] or entry['image_storage_key']),
        'recycled_image_prompt': (entry['recycled_image_prompt'] or ''),
        'image_position_x': _normalise_image_position(entry['image_position_x']),
        'image_position_y': _normalise_image_position(entry['image_position_y']),
        'image_source': 'ai',
    }), 200


@entries_bp.route('/daily/<int:entry_id>/image', methods=['POST'])
@jwt_required()
def upload_daily_image(entry_id):
    """Upload or replace a daily image for the entry."""
    user_id = int(get_jwt_identity())

    if 'image' not in request.files:
        return jsonify({'error': 'Upload an image file using the "image" field.'}), 400

    uploaded_file = request.files['image']
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'No image file was selected.'}), 400

    content_type = (uploaded_file.content_type or '').lower().strip()
    if content_type not in ALLOWED_ENTRY_IMAGE_MIME_TYPES:
        return jsonify({'error': 'Unsupported image type. Use JPG, PNG, or WEBP.'}), 400

    file_bytes = uploaded_file.read()
    if len(file_bytes) > MAX_ENTRY_IMAGE_UPLOAD_BYTES:
        return jsonify({'error': 'Image is too large. Maximum size is 5 MB.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, image_storage_key, recycled_image_prompt,
                  image_position_x, image_position_y, image_source
           FROM dailydiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    recycled_prompt = (
        (entry['image_prompt'] or '').strip()
        or (entry['recycled_image_prompt'] or '').strip()
    )

    try:
        image_bytes = _normalise_uploaded_entry_image(file_bytes)
        storage_key = store_uploaded_image(
            image_bytes,
            user_id=user_id,
            entry_kind='daily',
        )
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.error('Daily image upload failed for entry %s: %s', entry_id, exc)
        conn.close()
        return jsonify({'error': 'Image upload failed'}), 500

    cursor.execute(
        'UPDATE dailydiary_entries SET image_storage_key = ?, image_url = NULL, image_prompt = NULL, recycled_image_prompt = ?, image_source = ? WHERE id = ? AND user_id = ?',
        (storage_key, recycled_prompt or None, 'upload', entry_id, user_id),
    )
    conn.commit()
    conn.close()
    delete_image(entry['image_storage_key'])

    return jsonify({
        'id': entry_id,
        'image_prompt': '',
        'image_url': resolve_image_url(storage_key),
        'has_existing_image': bool(entry['image_url'] or entry['image_storage_key']),
        'recycled_image_prompt': recycled_prompt,
        'image_position_x': _normalise_image_position(entry['image_position_x']),
        'image_position_y': _normalise_image_position(entry['image_position_y']),
        'image_source': 'upload',
    }), 200


@entries_bp.route('/daily/<int:entry_id>/image', methods=['DELETE'])
@jwt_required()
def delete_daily_image(entry_id):
    """Delete only the current daily image, preserving the stored prompt."""
    user_id = int(get_jwt_identity())

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, image_storage_key, recycled_image_prompt, image_source
           FROM dailydiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    restored_prompt = (
        (entry['recycled_image_prompt'] or '').strip()
        or (entry['image_prompt'] or '').strip()
    )

    cursor.execute(
        'UPDATE dailydiary_entries SET image_storage_key = NULL, image_url = NULL, image_prompt = ?, recycled_image_prompt = NULL, image_position_x = 50, image_position_y = 50, image_source = NULL WHERE id = ? AND user_id = ?',
        (restored_prompt or None, entry_id, user_id),
    )
    conn.commit()
    conn.close()
    delete_image(entry['image_storage_key'])

    return jsonify({
        'id': entry_id,
        'image_prompt': restored_prompt,
        'image_url': None,
        'had_existing_image': bool(entry['image_url'] or entry['image_storage_key']),
        'recycled_image_prompt': '',
        'image_position_x': 50.0,
        'image_position_y': 50.0,
        'image_source': None,
    }), 200


@entries_bp.route('/daily/<int:entry_id>/attachments', methods=['POST'])
@jwt_required()
def upload_daily_attachment(entry_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _upload_entry_attachment(
        table_name='dailydiary_entries',
        entry_type='daily',
        entry_id=entry_id,
        user_id=user_id,
    )
    return jsonify(payload), status_code


@entries_bp.route('/daily/<int:entry_id>/attachments/<int:asset_id>', methods=['DELETE'])
@jwt_required()
def delete_daily_attachment(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _delete_entry_attachment(
        entry_type='daily',
        table_name='dailydiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
    )
    return jsonify(payload), status_code


@entries_bp.route('/daily/<int:entry_id>/attachments/<int:asset_id>/download', methods=['GET'])
@jwt_required()
def download_daily_attachment(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    return _download_entry_attachment(
        entry_type='daily',
        table_name='dailydiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
    )


@entries_bp.route('/daily/<int:entry_id>/attachments/<int:asset_id>/transcribe', methods=['POST'])
@jwt_required()
def transcribe_daily_attachment(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _transcribe_entry_attachment(
        entry_type='daily',
        table_name='dailydiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
    )
    return jsonify(payload), status_code


@entries_bp.route('/daily/<int:entry_id>/attachments/<int:asset_id>/derive-text', methods=['POST'])
@jwt_required()
def derive_daily_attachment_text(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _derive_pdf_attachment_text(
        entry_type='daily',
        table_name='dailydiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
        force_refresh=True,
    )
    return jsonify(payload), status_code

# Dream entries endpoints
@entries_bp.route('/dreams', methods=['GET'])
@jwt_required()
def get_dream_entries():
    """Get all dream entries for authenticated user."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entries = cursor.execute('''
        SELECT * FROM dreamdiary_entries
        WHERE user_id = ?
        ORDER BY entry_date DESC, COALESCE(entry_time, '08:00') DESC, entry_number DESC
    ''', (user_id,)).fetchall()
    attachment_summaries_by_id = _load_entry_asset_summary_map(
        conn,
        user_id=user_id,
        entry_type='dream',
    )
    
    payload = [
        _serialise_entry_row(
            conn,
            entry,
            table_name='dreamdiary_entries',
            entry_kind='dream',
            include_attachment_details=False,
            attachment_summaries_by_id=attachment_summaries_by_id,
            verify_media_exists=False,
        )
        for entry in entries
    ]
    conn.commit()
    conn.close()
    
    return jsonify(payload), 200

@entries_bp.route('/dreams/<int:entry_id>', methods=['GET'])
@jwt_required()
def get_dream_entry(entry_id):
    """Get specific dream entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    
    entry = cursor.execute('''
        SELECT * FROM dreamdiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id)).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    payload = _serialise_entry_row(
        conn,
        entry,
        table_name='dreamdiary_entries',
        entry_kind='dream',
        include_import_metadata=True,
    )
    conn.commit()
    conn.close()
    
    return jsonify(payload), 200

@entries_bp.route('/dreams', methods=['POST'])
@jwt_required()
def create_dream_entry():
    """Create new dream entry."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    entry_date = _normalise_entry_date(
        data.get('entry_date', datetime.now().strftime('%Y-%m-%d'))
    )
    entry_time = _normalise_entry_time(
        data.get('entry_time', datetime.now().strftime('%H:%M'))
    )
    if not entry_date:
        return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
    if not entry_time:
        return jsonify({'error': 'Invalid entry_time format. Use HH:MM'}), 400
    if _is_future_entry_date(entry_date):
        return jsonify({'error': 'Future entry dates are not allowed'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get next entry number for the day
    max_entry = cursor.execute('''
        SELECT MAX(entry_number) as max_num
        FROM dreamdiary_entries
        WHERE user_id = ? AND entry_date = ?
    ''', (user_id, entry_date)).fetchone()
    
    entry_number = (max_entry['max_num'] or 0) + 1
    dream_row_data = {
        'title': data.get('title', ''),
        'plot': data.get('plot', ''),
        'cast': data.get('cast', ''),
        'location': data.get('location', ''),
        'period': data.get('period', ''),
        'emotion': data.get('emotion', ''),
        'symbols_and_imagery': data.get('symbols_and_imagery', ''),
        'insight': data.get('insight', ''),
        'action': data.get('action', ''),
        'other': data.get('other', ''),
        'tags': data.get('tags', ''),
    }
    enrichment = _build_dream_save_enrichment(
        row_data=dream_row_data,
        user_tags=data.get('tags', ''),
        user_people=data.get('dream_people_names', ''),
        user_places=data.get('dream_places', ''),
    )
    
    # Insert with all dream-specific fields
    cursor.execute(append_returning_id('''
        INSERT INTO dreamdiary_entries 
        (user_id, entry_date, entry_time, entry_number, title, cast, location, 
         period, emotion, plot, symbols_and_imagery, insight, action, other, tags,
         mood, ai_style, dream_people_names, dream_places)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', _database_provider()), (
        user_id, entry_date, entry_time, entry_number,
        data.get('title', ''),
        data.get('cast', ''),
        data.get('location', ''),
        data.get('period', ''),
        data.get('emotion', ''),
        data.get('plot', ''),
        data.get('symbols_and_imagery', ''),
        data.get('insight', ''),
        data.get('action', ''),
        data.get('other', ''),
        enrichment['tags'],
        data.get('mood', ''),
        data.get('ai_style', ''),
        enrichment['dream_people_names'],
        enrichment['dream_places'],
    ))
    
    entry_id = inserted_id(cursor, _database_provider())
    conn.commit()
    conn.close()
    
    return jsonify({
        'id': entry_id,
        'entry_date': entry_date,
        'entry_time': entry_time,
        'entry_number': entry_number
    }), 201

@entries_bp.route('/dreams/<int:entry_id>', methods=['PUT'])
@jwt_required()
def update_dream_entry(entry_id):
    """Update dream entry with AI analysis results."""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Check ownership
    entry = cursor.execute(
        '''SELECT id, entry_date, title, "cast", location, period, emotion, plot,
                  symbols_and_imagery, insight, action, other, tags,
                  dream_people_names, dream_places
           FROM dreamdiary_entries WHERE id = ? AND user_id = ?''',
        (entry_id, user_id)
    ).fetchone()
    
    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404
    
    # Update allowed fields
    allowed_fields = [
        'title', 'cast', 'location', 'period', 'emotion', 'plot',
        'symbols_and_imagery', 'insight', 'action', 'other',
        'summary', 'interpretation', 'image_prompt', 'image_url',
        'mood', 'ai_style',
        'image_position_x', 'image_position_y', 'analysis_attachment_refs',
    ]
    
    updates = []
    values = []

    if 'entry_date' in data:
        parsed_entry_date = _normalise_entry_date(data.get('entry_date'))
        if not parsed_entry_date:
            conn.close()
            return jsonify({'error': 'Invalid entry_date format. Use YYYY-MM-DD'}), 400
        if _is_future_entry_date(parsed_entry_date):
            conn.close()
            return jsonify({'error': 'Future entry dates are not allowed'}), 400

        updates.append('entry_date = ?')
        values.append(parsed_entry_date)

        if parsed_entry_date != entry['entry_date']:
            max_entry = cursor.execute('''
                SELECT MAX(entry_number) as max_num
                FROM dreamdiary_entries
                WHERE user_id = ? AND entry_date = ?
            ''', (user_id, parsed_entry_date)).fetchone()
            entry_number = (max_entry['max_num'] or 0) + 1
            updates.append('entry_number = ?')
            values.append(entry_number)

    if 'entry_time' in data:
        parsed_entry_time = _normalise_entry_time(data.get('entry_time'))
        if not parsed_entry_time:
            conn.close()
            return jsonify({'error': 'Invalid entry_time format. Use HH:MM'}), 400
        updates.append('entry_time = ?')
        values.append(parsed_entry_time)
    
    for field in allowed_fields:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(_normalise_update_field_value(field, data[field]))

    dream_row_data = {
        'title': data.get('title', entry['title']),
        'plot': data.get('plot', entry['plot']),
        'cast': data.get('cast', entry['cast']),
        'location': data.get('location', entry['location']),
        'period': data.get('period', entry['period']),
        'emotion': data.get('emotion', entry['emotion']),
        'symbols_and_imagery': data.get('symbols_and_imagery', entry['symbols_and_imagery']),
        'insight': data.get('insight', entry['insight']),
        'action': data.get('action', entry['action']),
        'other': data.get('other', entry['other']),
        'tags': data.get('tags', entry['tags']),
    }
    enrichment = _build_dream_save_enrichment(
        row_data=dream_row_data,
        user_tags=data.get('tags', entry['tags']),
        user_people=data.get('dream_people_names', entry['dream_people_names']),
        user_places=data.get('dream_places', entry['dream_places']),
    )
    updates.extend([
        'tags = ?',
        'dream_people_names = ?',
        'dream_places = ?',
    ])
    values.extend([
        enrichment['tags'],
        enrichment['dream_people_names'],
        enrichment['dream_places'],
    ])
    
    if not updates:
        conn.close()
        return jsonify({'error': 'No fields to update'}), 400
    
    values.append(entry_id)
    values.append(user_id)
    
    cursor.execute(f'''
        UPDATE dreamdiary_entries
        SET {', '.join(updates)}
        WHERE id = ? AND user_id = ?
    ''', values)
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Entry updated'}), 200

@entries_bp.route('/dreams/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_dream_entry(entry_id):
    """Delete dream entry."""
    user_id = int(get_jwt_identity())
    
    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        'SELECT image_storage_key FROM dreamdiary_entries WHERE id = ? AND user_id = ?',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    attachment_keys = _delete_entry_assets(
        conn,
        user_id=user_id,
        entry_type='dream',
        entry_id=entry_id,
    )
    _unlink_cbt_worksheets(
        conn,
        user_id=user_id,
        entry_type='dream',
        entry_id=entry_id,
    )

    cursor.execute('''
        DELETE FROM dreamdiary_entries
        WHERE id = ? AND user_id = ?
    ''', (entry_id, user_id))
    
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    
    if deleted == 0:
        return jsonify({'error': 'Entry not found'}), 404

    delete_image(entry['image_storage_key'])
    for storage_key in attachment_keys:
        delete_image(storage_key)
    
    return '', 204


@entries_bp.route('/dreams/<int:entry_id>/generate-image', methods=['POST'])
@jwt_required()
def generate_dream_image(entry_id):
    """Generate or regenerate a dream image from the stored or overridden dream image prompt."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, image_storage_key, recycled_image_prompt,
                  image_position_x, image_position_y, image_source
           FROM dreamdiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    image_prompt_override = (data.get('image_prompt_override') or '').strip()
    image_prompt = image_prompt_override or (entry['image_prompt'] or '').strip()
    if not image_prompt:
        conn.close()
        return jsonify({'error': 'This dream entry does not yet have an image prompt.'}), 400

    quota_error = _check_usage_or_error(
        conn,
        user_id=user_id,
        event_type=AI_IMAGE_EVENT,
        units=1,
        message='This plan has reached its monthly AI image limit.',
    )
    if quota_error:
        conn.close()
        payload, status_code = quota_error
        return jsonify(payload), status_code

    try:
        ai_service = OpenAIService()
        image_bytes = ai_service.generate_image(image_prompt)
        storage_key = store_generated_image(
            image_bytes,
            user_id=user_id,
            entry_kind='dream',
        )
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 503
    except Exception as exc:
        current_app.logger.error('Dream image generation failed for entry %s: %s', entry_id, exc)
        conn.close()
        return jsonify({'error': 'Image generation failed'}), 502

    cursor.execute(
        'UPDATE dreamdiary_entries SET image_storage_key = ?, image_url = NULL, image_source = ? WHERE id = ? AND user_id = ?',
        (storage_key, 'ai', entry_id, user_id),
    )
    _record_usage_safely(
        conn,
        user_id=user_id,
        event_type=AI_IMAGE_EVENT,
        metadata={'entry_type': 'dream', 'entry_id': entry_id},
    )
    conn.commit()
    conn.close()
    delete_image(entry['image_storage_key'])

    return jsonify({
        'id': entry_id,
        'image_prompt': image_prompt,
        'image_url': resolve_image_url(storage_key),
        'has_existing_image': bool(entry['image_url'] or entry['image_storage_key']),
        'recycled_image_prompt': (entry['recycled_image_prompt'] or ''),
        'image_position_x': _normalise_image_position(entry['image_position_x']),
        'image_position_y': _normalise_image_position(entry['image_position_y']),
        'image_source': 'ai',
    }), 200


@entries_bp.route('/dreams/<int:entry_id>/image', methods=['POST'])
@jwt_required()
def upload_dream_image(entry_id):
    """Upload or replace a dream image for the entry."""
    user_id = int(get_jwt_identity())

    if 'image' not in request.files:
        return jsonify({'error': 'Upload an image file using the "image" field.'}), 400

    uploaded_file = request.files['image']
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({'error': 'No image file was selected.'}), 400

    content_type = (uploaded_file.content_type or '').lower().strip()
    if content_type not in ALLOWED_ENTRY_IMAGE_MIME_TYPES:
        return jsonify({'error': 'Unsupported image type. Use JPG, PNG, or WEBP.'}), 400

    file_bytes = uploaded_file.read()
    if len(file_bytes) > MAX_ENTRY_IMAGE_UPLOAD_BYTES:
        return jsonify({'error': 'Image is too large. Maximum size is 5 MB.'}), 400

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, image_storage_key, recycled_image_prompt,
                  image_position_x, image_position_y, image_source
           FROM dreamdiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    recycled_prompt = (
        (entry['image_prompt'] or '').strip()
        or (entry['recycled_image_prompt'] or '').strip()
    )

    try:
        image_bytes = _normalise_uploaded_entry_image(file_bytes)
        storage_key = store_uploaded_image(
            image_bytes,
            user_id=user_id,
            entry_kind='dream',
        )
    except ValueError as exc:
        conn.close()
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        current_app.logger.error('Dream image upload failed for entry %s: %s', entry_id, exc)
        conn.close()
        return jsonify({'error': 'Image upload failed'}), 500

    cursor.execute(
        'UPDATE dreamdiary_entries SET image_storage_key = ?, image_url = NULL, image_prompt = NULL, recycled_image_prompt = ?, image_source = ? WHERE id = ? AND user_id = ?',
        (storage_key, recycled_prompt or None, 'upload', entry_id, user_id),
    )
    conn.commit()
    conn.close()
    delete_image(entry['image_storage_key'])

    return jsonify({
        'id': entry_id,
        'image_prompt': '',
        'image_url': resolve_image_url(storage_key),
        'has_existing_image': bool(entry['image_url'] or entry['image_storage_key']),
        'recycled_image_prompt': recycled_prompt,
        'image_position_x': _normalise_image_position(entry['image_position_x']),
        'image_position_y': _normalise_image_position(entry['image_position_y']),
        'image_source': 'upload',
    }), 200


@entries_bp.route('/dreams/<int:entry_id>/image', methods=['DELETE'])
@jwt_required()
def delete_dream_image(entry_id):
    """Delete only the current dream image, preserving the stored prompt."""
    user_id = int(get_jwt_identity())

    conn = get_db()
    cursor = conn.cursor()
    entry = cursor.execute(
        '''SELECT id, image_prompt, image_url, image_storage_key, recycled_image_prompt, image_source
           FROM dreamdiary_entries
           WHERE id = ? AND user_id = ?''',
        (entry_id, user_id),
    ).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Entry not found'}), 404

    restored_prompt = (
        (entry['recycled_image_prompt'] or '').strip()
        or (entry['image_prompt'] or '').strip()
    )

    cursor.execute(
        'UPDATE dreamdiary_entries SET image_storage_key = NULL, image_url = NULL, image_prompt = ?, recycled_image_prompt = NULL, image_position_x = 50, image_position_y = 50, image_source = NULL WHERE id = ? AND user_id = ?',
        (restored_prompt or None, entry_id, user_id),
    )
    conn.commit()
    conn.close()
    delete_image(entry['image_storage_key'])

    return jsonify({
        'id': entry_id,
        'image_prompt': restored_prompt,
        'image_url': None,
        'had_existing_image': bool(entry['image_url'] or entry['image_storage_key']),
        'recycled_image_prompt': '',
        'image_position_x': 50.0,
        'image_position_y': 50.0,
        'image_source': None,
    }), 200


@entries_bp.route('/dreams/<int:entry_id>/attachments', methods=['POST'])
@jwt_required()
def upload_dream_attachment(entry_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _upload_entry_attachment(
        table_name='dreamdiary_entries',
        entry_type='dream',
        entry_id=entry_id,
        user_id=user_id,
    )
    return jsonify(payload), status_code


@entries_bp.route('/dreams/<int:entry_id>/attachments/<int:asset_id>', methods=['DELETE'])
@jwt_required()
def delete_dream_attachment(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _delete_entry_attachment(
        entry_type='dream',
        table_name='dreamdiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
    )
    return jsonify(payload), status_code


@entries_bp.route('/dreams/<int:entry_id>/attachments/<int:asset_id>/download', methods=['GET'])
@jwt_required()
def download_dream_attachment(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    return _download_entry_attachment(
        entry_type='dream',
        table_name='dreamdiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
    )


@entries_bp.route('/dreams/<int:entry_id>/attachments/<int:asset_id>/transcribe', methods=['POST'])
@jwt_required()
def transcribe_dream_attachment(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _transcribe_entry_attachment(
        entry_type='dream',
        table_name='dreamdiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
    )
    return jsonify(payload), status_code


@entries_bp.route('/dreams/<int:entry_id>/attachments/<int:asset_id>/derive-text', methods=['POST'])
@jwt_required()
def derive_dream_attachment_text(entry_id, asset_id):
    user_id = int(get_jwt_identity())
    payload, status_code = _derive_pdf_attachment_text(
        entry_type='dream',
        table_name='dreamdiary_entries',
        entry_id=entry_id,
        asset_id=asset_id,
        user_id=user_id,
        force_refresh=True,
    )
    return jsonify(payload), status_code


@entries_bp.route('/entries/bulk-delete-readiness', methods=['GET'])
@jwt_required()
def get_bulk_delete_readiness():
    """Return whether the current user can bulk-delete all entries."""
    user_id = int(get_jwt_identity())
    guard_token = (request.args.get('guard_token') or '').strip() or None

    conn = get_db()
    readiness = _build_bulk_delete_readiness(conn, user_id, guard_token)
    conn.close()

    return jsonify(readiness), 200


@entries_bp.route('/entries/delete-selected', methods=['POST'])
@jwt_required()
def delete_selected_entries():
    """Delete an explicit, ownership-checked set of daily and dream entries."""
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    selected = data.get('entries', [])
    if not isinstance(selected, list) or not selected:
        return jsonify({'error': 'Select at least one entry to delete.'}), 400
    if len(selected) > 500:
        return jsonify({'error': 'Delete at most 500 entries at a time.'}), 400

    normalised: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    for item in selected:
        if not isinstance(item, dict) or item.get('type') not in {'daily', 'dream'}:
            return jsonify({'error': 'Each selected entry needs a valid type and id.'}), 400
        try:
            key = (str(item['type']), int(item['id']))
        except (KeyError, TypeError, ValueError):
            return jsonify({'error': 'Each selected entry needs a valid type and id.'}), 400
        if key[1] <= 0:
            return jsonify({'error': 'Each selected entry needs a valid type and id.'}), 400
        if key not in seen:
            seen.add(key)
            normalised.append(key)

    conn = get_db()
    storage_keys: list[str] = []
    deleted = {'daily': 0, 'dream': 0}
    try:
        for entry_type, entry_id in normalised:
            table_name = 'dailydiary_entries' if entry_type == 'daily' else 'dreamdiary_entries'
            row = conn.execute(
                f'SELECT image_storage_key FROM {table_name} WHERE id = ? AND user_id = ?',
                (entry_id, user_id),
            ).fetchone()
            if not row:
                continue
            if row['image_storage_key']:
                storage_keys.append(str(row['image_storage_key']))
            storage_keys.extend(_delete_entry_assets(
                conn,
                user_id=user_id,
                entry_type=entry_type,
                entry_id=entry_id,
            ))
            _unlink_cbt_worksheets(
                conn,
                user_id=user_id,
                entry_type=entry_type,
                entry_id=entry_id,
            )
            deleted[entry_type] += conn.execute(
                f'DELETE FROM {table_name} WHERE id = ? AND user_id = ?',
                (entry_id, user_id),
            ).rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()

    for storage_key in storage_keys:
        delete_image(storage_key)
    return jsonify({
        'deleted_daily': deleted['daily'],
        'deleted_dreams': deleted['dream'],
        'deleted_total': deleted['daily'] + deleted['dream'],
    }), 200


@entries_bp.route('/entries/bulk-delete', methods=['POST'])
@jwt_required()
def bulk_delete_entries():
    """Delete all journal data for the current user after guarded export."""
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    guard_token = str(data.get('guard_token') or '').strip()
    confirmation_text = str(data.get('confirmation_text') or '').strip()

    if confirmation_text != 'DELETE ALL':
        return jsonify({'error': 'Type DELETE ALL to confirm bulk delete.'}), 400

    conn = get_db()
    readiness = _build_bulk_delete_readiness(conn, user_id, guard_token)
    if not readiness['eligible_for_delete']:
        conn.close()
        return jsonify({
            'error': 'A same-session full export of all journal data is required before bulk delete.',
            'readiness': readiness,
        }), 409

    guard_record = get_latest_bulk_delete_guard(conn, user_id, guard_token)
    image_rows = conn.execute(
        '''
        SELECT image_storage_key AS storage_key FROM dailydiary_entries WHERE user_id = ? AND image_storage_key IS NOT NULL
        UNION ALL
        SELECT image_storage_key AS storage_key FROM dreamdiary_entries WHERE user_id = ? AND image_storage_key IS NOT NULL
        UNION ALL
        SELECT image_storage_key AS storage_key FROM important_days WHERE user_id = ? AND image_storage_key IS NOT NULL
        UNION ALL
        SELECT storage_key FROM entry_assets WHERE user_id = ?
        ''',
        (user_id, user_id, user_id, user_id),
    ).fetchall()
    storage_keys = [str(row['storage_key'] or '').strip() for row in image_rows if row['storage_key']]
    conn.execute('DELETE FROM entry_assets WHERE user_id = ?', (user_id,))
    _unlink_cbt_worksheets(conn, user_id=user_id)
    thought_record_data_deleted = conn.execute(
        '''
        DELETE FROM cbt_thought_record_data
        WHERE worksheet_id IN (
            SELECT id FROM cbt_worksheets WHERE user_id = ?
        )
        ''',
        (user_id,),
    ).rowcount
    thought_record_deleted = conn.execute(
        'DELETE FROM cbt_worksheets WHERE user_id = ?',
        (user_id,),
    ).rowcount
    important_day_deleted = conn.execute(
        'DELETE FROM important_days WHERE user_id = ?',
        (user_id,),
    ).rowcount
    daily_deleted = conn.execute(
        'DELETE FROM dailydiary_entries WHERE user_id = ?',
        (user_id,),
    ).rowcount
    dream_deleted = conn.execute(
        'DELETE FROM dreamdiary_entries WHERE user_id = ?',
        (user_id,),
    ).rowcount
    if guard_record:
        mark_export_guard_used(conn, int(guard_record['id']))
    else:
        conn.commit()
    conn.close()

    for storage_key in storage_keys:
        delete_image(storage_key)

    return jsonify({
        'message': 'All journal data deleted.',
        'deleted_daily': daily_deleted,
        'deleted_dreams': dream_deleted,
        'deleted_important_days': important_day_deleted,
        'deleted_thought_records': thought_record_deleted,
        'deleted_thought_record_data': thought_record_data_deleted,
        'deleted_total': (
            daily_deleted
            + dream_deleted
            + important_day_deleted
            + thought_record_deleted
        ),
    }), 200


@entries_bp.route('/search', methods=['GET'])
@jwt_required()
def search_entries():
    """Search diary entries by content, tags, AI response, and metadata."""
    user_id = int(get_jwt_identity())
    query = (request.args.get('q') or '').strip()
    filters_param = (request.args.get('filters') or '').strip()

    if not query:
        return jsonify({
            'query': query,
            'filters': [],
            'filters_display': 'All Entries',
            'results': []
        }), 200

    filter_tokens = [token.strip().lower() for token in filters_param.split(',') if token.strip()]
    valid_filters = {'tags', 'date', 'keywords', 'people'}
    active_filters = {token for token in filter_tokens if token in valid_filters}
    include_all = not active_filters

    filter_labels = {
        'tags': 'Tags',
        'date': 'Date',
        'keywords': 'Keywords',
        'people': "People's Names"
    }
    filters_display = 'All Entries' if include_all else ', '.join(filter_labels[f] for f in active_filters)

    conn = get_db()
    try:
        cursor = conn.cursor()

        daily_rows = cursor.execute(_sql('''
            SELECT id, entry_date, title, user_message, ai_response, tags, daily_people_names
            FROM dailydiary_entries
            WHERE user_id = ?
        '''), (user_id,)).fetchall()

        dream_rows = cursor.execute(_sql('''
            SELECT id, entry_date, title, plot, interpretation, tags, dream_people_names
            FROM dreamdiary_entries
            WHERE user_id = ?
        '''), (user_id,)).fetchall()
    finally:
        conn.close()

    results = []
    parsed_query = _parse_search_query(query)
    query_terms = parsed_query['terms']
    query_mode = parsed_query['mode']
    phrase_text = parsed_query['phrase_text']

    def field_enabled(field_name: str) -> bool:
        if include_all:
            return True
        mapping = {
            'body': None,
            'ai': 'keywords',
            'tags': 'tags',
            'people': 'people',
            'date': 'date'
        }
        mapped = mapping.get(field_name)
        if mapped is None:
            return include_all
        return mapped in active_filters

    def process_entry(entry_type: str, base_data: dict) -> None:
        text_body = _coerce_search_text(base_data.get('body'))
        ai_text = _coerce_search_text(base_data.get('ai'))
        tags_text = _coerce_search_text(base_data.get('tags'))
        people_text = _coerce_search_text(base_data.get('people'))
        entry_date_obj = base_data.get('date_obj')
        entry_date_iso = entry_date_obj.date().isoformat() if entry_date_obj else str(base_data.get('entry_date') or '')
        title_plain = _coerce_search_text(base_data.get('title_plain'))

        searchable_fields = [title_plain]
        if field_enabled('body'):
            searchable_fields.append(text_body)
        if field_enabled('tags'):
            searchable_fields.append(tags_text)
        if field_enabled('people'):
            searchable_fields.append(people_text)
        if field_enabled('ai'):
            searchable_fields.append(ai_text)
        date_strings = _format_date_strings(entry_date_obj) if field_enabled('date') and entry_date_obj else []
        searchable_fields.extend(date_strings)
        searchable_text = ' '.join(str(value).lower() for value in searchable_fields if value)
        matched_terms = [
            term
            for term in query_terms
            if _search_term_matches(searchable_text, term['text'], phrase=term['phrase'])
        ]
        exact_phrase_match = bool(
            phrase_text
            and _search_term_matches(searchable_text, phrase_text, phrase=True)
        )
        if not query_terms:
            return
        if query_mode in {'and', 'phrase'} and len(matched_terms) != len(query_terms):
            return
        if query_mode == 'or' and not matched_terms:
            return

        highlight_terms = (
            [{'text': phrase_text, 'phrase': True}]
            if query_mode == 'phrase' and phrase_text
            else matched_terms
        )

        matches = {}
        matched = False

        # Check title match (always enabled as it's core content)
        highlighted = _highlight_inline_terms(title_plain, highlight_terms)
        if highlighted:
            matches['title'] = highlighted
            matched = True

        if field_enabled('body'):
            highlighted = _highlight_text_terms(text_body, highlight_terms)
            if highlighted:
                matches['body'] = highlighted
                matched = True

        if field_enabled('tags') and tags_text:
            highlighted = _highlight_inline_terms(tags_text, highlight_terms)
            if highlighted:
                matches['tags'] = highlighted
                matched = True

        if field_enabled('people') and people_text:
            highlighted = _highlight_inline_terms(people_text, highlight_terms)
            if highlighted:
                matches['people'] = highlighted
                matched = True

        if field_enabled('ai') and ai_text:
            highlighted = _highlight_text_terms(ai_text, highlight_terms)
            if highlighted:
                matches['ai'] = highlighted
                matched = True

        if field_enabled('date') and entry_date_obj:
            for date_str in date_strings:
                highlighted = _highlight_inline_terms(date_str, highlight_terms)
                if highlighted:
                    matches['date'] = highlighted
                    matched = True
                    break

        if not matched:
            return

        # Use the title match if found, otherwise escape plain title
        title_highlight = matches.get('title') or escape(title_plain)
        entry_date_display = entry_date_obj.strftime('%d/%m/%Y') if entry_date_obj else ''

        results.append({
            'id': base_data['id'],
            'type': entry_type,
            'title': title_plain,
            'title_highlight': title_highlight,
            'entry_date': entry_date_iso,
            'entry_date_display': entry_date_display,
            'tags': tags_text,
            'matches': matches,
            'score': (
                (100 if exact_phrase_match else 0)
                + (len(matched_terms) * 10)
                + (5 if matches.get('title') else 0)
                + (3 if matches.get('tags') else 0)
            ),
        })

    for row in daily_rows:
        entry_date_obj = _parse_entry_date(row['entry_date'])
        user_message = row['user_message'] or ''
        
        # Use database title field, fallback to first line of user_message
        db_title = (row['title'] or '').strip()
        if db_title:
            title_plain = db_title
        else:
            # Fallback: use first line of user_message
            parts = user_message.split('\n', 1)
            title_plain = parts[0].strip('" ') if parts[0].strip() else 'Daily Entry'
        
        base_data = {
            'id': row['id'],
            'entry_date': row['entry_date'],
            'date_obj': entry_date_obj,
            'title_plain': title_plain,
            'body': user_message,
            'ai': row['ai_response'] or '',
            'tags': row['tags'] or '',
            'people': row['daily_people_names'] or ''
        }
        process_entry('daily', base_data)

    for row in dream_rows:
        entry_date_obj = _parse_entry_date(row['entry_date'])
        base_data = {
            'id': row['id'],
            'entry_date': row['entry_date'],
            'date_obj': entry_date_obj,
            'title_plain': (row['title'] or 'Dream Entry').strip('" '),
            'body': row['plot'] or '',
            'ai': row['interpretation'] or '',
            'tags': row['tags'] or '',
            'people': row['dream_people_names'] or ''
        }
        process_entry('dream', base_data)

    results.sort(key=lambda item: (item.get('score', 0), item['entry_date']), reverse=True)
    truncated = len(results) > SEARCH_RESULT_LIMIT
    if truncated:
        results = results[:SEARCH_RESULT_LIMIT]

    return jsonify({
        'query': query,
        'filters': list(active_filters),
        'filters_display': filters_display,
        'results': [
            {key: value for key, value in result.items() if key != 'score'}
            for result in results
        ],
        'truncated': truncated,
        'result_limit': SEARCH_RESULT_LIMIT,
    }), 200

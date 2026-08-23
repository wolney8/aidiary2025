# server/services/import_service.py
# Excel import service: validation, parsing, duplicate handling, history tracking
import io
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import secrets
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime, date, time, timezone
from collections import Counter
from collections.abc import Callable, Mapping
from services.nltk_enrichment import (
    derive_daily_nltk_fields as _runtime_derive_daily_nltk_fields,
    derive_dream_nltk_fields as _runtime_derive_dream_nltk_fields,
)
from services.database import table_columns, table_info
from services.media_storage import store_entry_asset, store_imported_image
from services.import_adapters import get_import_adapter
from services.sql_compat import append_returning_id, inserted_id

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {'.xlsx', '.zip'}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/octet-stream',  # generic binary used by some clients
    'application/zip',
    'application/x-zip-compressed',
}


def _connection_provider(conn: sqlite3.Connection) -> str:
    return str(getattr(conn, 'database_provider', 'sqlite') or 'sqlite')


def _cursor_provider(cursor: sqlite3.Cursor) -> str:
    connection = getattr(cursor, 'connection', None)
    if connection is None:
        return 'sqlite'
    return _connection_provider(connection)


def _row_value(row: object, index: int, key: str) -> object:
    """Read a selected column from SQLite sequence rows or Postgres mapping rows."""
    if isinstance(row, Mapping):
        return row.get(key)
    return row[index]

DAILY_REQUIRED_HEADERS = ('date', 'title', 'user_entry', 'ai_response')
DAILY_OPTIONAL_HEADERS = ('entry_time', 'entry_asset_ref')
DAILY_IMPORT_HEADERS = ('date', 'entry_time', 'title', 'user_entry', 'ai_response', 'entry_asset_ref')
DREAM_IMPORT_HEADERS = (
    'date',
    'entry_time',
    'title',
    'plot',
    'cast',
    'location',
    'period',
    'emotion',
    'symbols_and_imagery',
    'insight',
    'action',
    'other',
    'tags',
    'entry_asset_ref',
)
IMPORTANT_DAY_IMPORT_HEADERS = (
    'starts_on',
    'label',
    'category',
    'recurrence',
    'icon_name',
    'accent_color',
    'note',
    'entry_asset_ref',
)
THOUGHT_RECORD_IMPORT_HEADERS = (
    'record_date',
    'title',
    'status',
    'current_step',
    'linked_entry_type',
    'linked_entry_id',
    'situation',
    'feelings_before',
    'unhelpful_thoughts',
    'evidence_for',
    'evidence_against',
    'balanced_thought',
    'feelings_after',
    'next_step',
    'ai_response',
    'ai_responded_at',
    'ai_response_outdated',
)
_DREAM_REQUIRED_HEADERS = tuple(
    header for header in DREAM_IMPORT_HEADERS if header not in {'entry_time', 'entry_asset_ref'}
)

# Script-injection patterns to strip from cell values
_INJECTION_PATTERNS = re.compile(r'[<>]|javascript:', re.IGNORECASE)
_FORMULA_PREFIXES = ('=', '+', '-', '@')
_DUPLICATE_TAG = '*Duplicate*'
_DEFAULT_IMPORT_TIMES = {
    'daily': '19:00',
    'dream': '08:00',
}
_PACKAGE_WORKBOOK_NAME = 'entries.xlsx'
_PACKAGE_MANIFEST_NAME = 'manifest.json'
PACKAGE_TYPE = 'openmynd_export'
LEGACY_PACKAGE_TYPES = {'aidiary_export'}
PACKAGE_FORMAT_VERSION = 1
PORTABILITY_CONTRACT = {
    'contract_version': 1,
    'workbook_fields': {
        'daily': list(DAILY_IMPORT_HEADERS),
        'dream': list(DREAM_IMPORT_HEADERS),
        'important_days': list(IMPORTANT_DAY_IMPORT_HEADERS),
        'thought_records': list(THOUGHT_RECORD_IMPORT_HEADERS),
    },
    'preserved_assets': [
        'hero images and framing metadata',
        'entry attachments and their filenames, MIME types, and ordering',
        'important days and their images',
        'thought records and their AI responses',
    ],
    'normalised_on_import': [
        'blank Daily entry times default to 19:00',
        'blank Dream entry times default to 08:00',
        'search enrichment metadata is recalculated from imported entry text',
    ],
    'omitted_data': [
        'account and Customisation settings',
        'public-holiday preferences',
        'chat history',
        'attachment-derived text and transcripts',
        'Daily mood and derived tags, people, and places',
        'Dream AI summary and interpretation',
    ],
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_file(
    filename: str,
    content_type: str,
    file_size: int,
    *,
    source: str = 'aidiary',
) -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    if not filename:
        errors.append('No filename provided.')
        return errors

    ext = _file_extension(filename)
    adapter = get_import_adapter(source) if source != 'aidiary' else None
    allowed_extensions = adapter.extensions if adapter else ALLOWED_EXTENSIONS
    allowed_mime_types = adapter.mime_types if adapter else ALLOWED_MIME_TYPES
    if source != 'aidiary' and not adapter:
        errors.append(f'Unsupported import source "{source}".')
        return errors
    if ext not in allowed_extensions:
        errors.append(
            f'Invalid file type "{ext}" for {source} import.'
        )

    if content_type and content_type not in allowed_mime_types:
        errors.append(
            f'Invalid content type "{content_type}" for {source} import.'
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        limit_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        errors.append(
            f'File size {file_size / (1024 * 1024):.1f} MB exceeds the {limit_mb} MB limit.'
        )

    if file_size == 0:
        errors.append('Uploaded file is empty.')

    return errors


def _file_extension(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith('.xlsx'):
        return '.xlsx'
    dot = lower.rfind('.')
    return lower[dot:] if dot != -1 else ''


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------

def _is_blankish(value) -> bool:
    """Return True for None/NaN/blank-like spreadsheet values."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True

    text = str(value).strip()
    if not text:
        return True

    return text.lower() in {'nan', 'none', '<na>', 'nat'}


def _sanitise(value) -> str:
    """Convert cell value to a clean string, removing injection vectors."""
    if _is_blankish(value):
        return ''
    text = str(value).strip()
    if text.startswith(_FORMULA_PREFIXES):
        text = text[1:].lstrip()
    return _INJECTION_PATTERNS.sub('', text)


def _normalise_title_key(value: str) -> str:
    """Collapse title casing/spacing so duplicate checks are less brittle."""
    return ' '.join((value or '').strip().lower().split())


def _normalise_content_key(value: str) -> str:
    """Collapse content casing/spacing so duplicate checks can use main body text."""
    return ' '.join((value or '').strip().lower().split())


def _normalise_time_key(value: str, *, entry_type: str) -> str:
    """Normalise import times so same-day entries remain distinct by time."""
    return (value or _DEFAULT_IMPORT_TIMES[entry_type]).strip()[:5]


def _truncate_preview(value: str, limit: int = 96) -> str:
    text = ' '.join((value or '').strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + '…'


def _normalise_headers(columns) -> list[str]:
    return [str(column).strip().lower() for column in columns]


def _parse_json_array(value, *, fallback=None):
    if fallback is None:
        fallback = []
    if _is_blankish(value):
        return fallback
    if isinstance(value, list):
        return value
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, list) else fallback


def _json_cell(value) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value or [], ensure_ascii=True)
    except (TypeError, ValueError):
        return '[]'


def _coerce_int_cell(
    value,
    *,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _coerce_allowed_cell(value, allowed: set[str], default: str) -> str:
    text = _sanitise(value).strip().lower()
    return text if text in allowed else default


def _parse_boolish_cell(value) -> int:
    text = str(value or '').strip().lower()
    return 1 if text in {'1', 'true', 'yes', 'y'} else 0


def _normalise_header_set(columns: list[str]) -> set[str]:
    return {column for column in columns if column}


def _validate_sheet_headers(
    sheet_name: str,
    columns: list[str],
    required_headers: tuple[str, ...],
    optional_headers: tuple[str, ...] = (),
) -> list[str]:
    warnings: list[str] = []
    accepted_headers = set(required_headers) | set(optional_headers)
    missing = [header for header in required_headers if header not in columns]
    unexpected = [column for column in columns if column and column not in accepted_headers]

    if missing:
        warnings.append(
            f"{sheet_name} sheet: missing columns {', '.join(missing)}. "
            "Rows missing required data may be skipped."
        )

    if unexpected:
        warnings.append(
            f"{sheet_name} sheet: ignoring unexpected columns {', '.join(unexpected)}."
        )

    return warnings


def _validate_daily_headers_strict(columns: list[str]) -> list[str]:
    required = set(DAILY_REQUIRED_HEADERS)
    full = set(DAILY_IMPORT_HEADERS)
    actual = _normalise_header_set(columns)
    header_counts = Counter(columns)
    duplicates = [name for name, count in header_counts.items() if name and count > 1]

    if actual in (required, full) and not duplicates:
        return []

    missing = sorted(required - actual)
    unexpected = sorted(actual - full)
    details: list[str] = []
    if missing:
        details.append(f"missing columns: {', '.join(missing)}")
    if unexpected:
        details.append(f"unexpected columns: {', '.join(unexpected)}")
    if duplicates:
        details.append(f"duplicate columns: {', '.join(sorted(duplicates))}")

    details_str = '; '.join(details) if details else 'header mismatch'
    found_headers = ', '.join(columns)
    return [
        'Daily sheet headers must exactly match: '
        + ', '.join(DAILY_IMPORT_HEADERS)
        + f'. Found: {found_headers}. {details_str}.'
    ]


def _parse_date(value) -> str | None:
    """Parse various date representations into ISO 'YYYY-MM-DD' string."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime('%Y-%m-%d')
    text = str(value).strip()
    # pandas converts Excel date cells to 'YYYY-MM-DD HH:MM:SS' when dtype=str
    if ' ' in text:
        text = text.split(' ')[0]
    if 'T' in text:
        text = text.split('T')[0]
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _parse_time(value, *, default: str) -> str | None:
    """Parse spreadsheet time values into HH:MM, defaulting only for blank cells."""
    if _is_blankish(value):
        return default

    if isinstance(value, datetime):
        return value.strftime('%H:%M')
    if isinstance(value, time):
        return value.strftime('%H:%M')

    text = str(value).strip()
    if 'T' in text:
        text = text.split('T')[-1]
    if ' ' in text:
        text = text.split(' ')[-1]

    for fmt in ('%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M:%S %p'):
        try:
            return datetime.strptime(text, fmt).strftime('%H:%M')
        except ValueError:
            continue

    return None


def _derive_daily_nltk_fields(
    title: str,
    user_message: str,
    *,
    source_app: str = '',
) -> dict[str, str]:
    excluded_terms = {source_app} if source_app else None
    return _runtime_derive_daily_nltk_fields(
        title,
        user_message,
        excluded_terms=excluded_terms,
    )


def _derive_dream_nltk_fields(row_data: dict[str, str]) -> dict[str, str]:
    return _runtime_derive_dream_nltk_fields(row_data)


# ---------------------------------------------------------------------------
# Excel / package parsing
# ---------------------------------------------------------------------------

def _get_package_staging_root() -> str:
    return tempfile.mkdtemp(prefix='openmynd-import-package-')


def _load_package_manifest(zip_file: zipfile.ZipFile) -> dict:
    if _PACKAGE_MANIFEST_NAME not in zip_file.namelist():
        return {}

    try:
        return json.loads(zip_file.read(_PACKAGE_MANIFEST_NAME).decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f'Could not read {_PACKAGE_MANIFEST_NAME}: {exc}') from exc


def _stage_package_asset(
    zip_file: zipfile.ZipFile,
    staging_root: str,
    asset_ref: str,
    package_filename: str,
) -> str | None:
    package_path = f'media/{asset_ref}/{package_filename}'
    try:
        package_bytes = zip_file.read(package_path)
    except KeyError:
        return None

    staged_dir = Path(staging_root) / asset_ref
    staged_dir.mkdir(parents=True, exist_ok=True)
    staged_path = staged_dir / Path(package_filename).name
    staged_path.write_bytes(package_bytes)
    return str(staged_path)


def _attach_package_asset_metadata(
    rows: list[dict],
    *,
    entry_type: str,
    manifest_assets: dict,
    zip_file: zipfile.ZipFile,
    staging_root: str,
    warnings: list[str],
) -> None:
    for row in rows:
        asset_ref = _sanitise(row.get('entry_asset_ref', ''))
        if not asset_ref:
            continue

        asset_meta = manifest_assets.get(asset_ref)
        if not isinstance(asset_meta, dict):
            warnings.append(
                f'{entry_type.title()} entry "{row.get("title", "") or row.get("entry_date", "")}": '
                f'missing manifest metadata for asset ref "{asset_ref}".'
            )
            continue

        image_filename = _sanitise(asset_meta.get('image_filename', ''))
        if image_filename:
            staged_path = _stage_package_asset(zip_file, staging_root, asset_ref, image_filename)
            if not staged_path:
                warnings.append(
                    f'{entry_type.title()} entry "{row.get("title", "") or row.get("entry_date", "")}": '
                    f'missing packaged image file "{image_filename}".'
                )
            else:
                row['import_image_path'] = staged_path
                row['image_source'] = _sanitise(asset_meta.get('image_source', '')) or 'upload'
                row['image_position_x'] = _sanitise(asset_meta.get('image_position_x', '')) or '50'
                row['image_position_y'] = _sanitise(asset_meta.get('image_position_y', '')) or '50'
                row['image_prompt'] = _sanitise(asset_meta.get('image_prompt', ''))
                row['recycled_image_prompt'] = _sanitise(asset_meta.get('recycled_image_prompt', ''))

        attachment_items = asset_meta.get('attachments', [])
        if not isinstance(attachment_items, list):
            continue

        staged_attachments: list[dict[str, str | int]] = []
        for attachment_meta in attachment_items:
            if not isinstance(attachment_meta, dict):
                continue

            attachment_filename = _sanitise(attachment_meta.get('package_filename', ''))
            if not attachment_filename:
                continue

            staged_attachment_path = _stage_package_asset(
                zip_file,
                staging_root,
                asset_ref,
                attachment_filename,
            )
            if not staged_attachment_path:
                warnings.append(
                    f'{entry_type.title()} entry "{row.get("title", "") or row.get("entry_date", "")}": '
                    f'missing packaged attachment file "{attachment_filename}".'
                )
                continue

            staged_attachments.append(
                {
                    'staged_path': staged_attachment_path,
                    'original_filename': _sanitise(attachment_meta.get('original_filename', ''))
                    or Path(attachment_filename).name,
                    'mime_type': _sanitise(attachment_meta.get('mime_type', '')),
                    'asset_role': _sanitise(attachment_meta.get('asset_role', '')) or 'attachment',
                    'sort_order': int(attachment_meta.get('sort_order', 0) or 0),
                    'file_size_bytes': int(attachment_meta.get('file_size_bytes', 0) or 0),
                }
            )

        if staged_attachments:
            row['import_attachment_files'] = staged_attachments


def parse_import_file(
    file_bytes: bytes,
    *,
    filename: str,
    source: str = 'aidiary',
) -> dict:
    adapter = get_import_adapter(source) if source != 'aidiary' else None
    if adapter:
        return adapter.parse(file_bytes, filename=filename)
    extension = _file_extension(filename)
    if extension == '.zip':
        return parse_import_package(file_bytes)
    return parse_excel_workbook(file_bytes)


def parse_import_package(file_bytes: bytes) -> dict:
    try:
        zip_buffer = io.BytesIO(file_bytes)
        with zipfile.ZipFile(zip_buffer) as zip_file:
            if _PACKAGE_WORKBOOK_NAME not in zip_file.namelist():
                raise ValueError(f'Zip package must contain {_PACKAGE_WORKBOOK_NAME}.')

            workbook_bytes = zip_file.read(_PACKAGE_WORKBOOK_NAME)
            parsed = parse_excel_workbook(workbook_bytes)
            if parsed.get('errors'):
                return parsed

            manifest = _load_package_manifest(zip_file)
            manifest_assets = manifest.get('assets', {}) if isinstance(manifest, dict) else {}
            manifest_warnings = parsed.setdefault('warnings', [])
            if manifest and not isinstance(manifest, dict):
                manifest_warnings.append(
                    'Package manifest is not an object; media metadata and portability details were ignored.'
                )
            elif isinstance(manifest, dict) and manifest:
                package_type = manifest.get('package_type')
                if package_type and package_type not in {PACKAGE_TYPE, *LEGACY_PACKAGE_TYPES}:
                    manifest_warnings.append(
                        f'Package type "{package_type}" is not the standard OpenMynd export type; '
                        'only recognised workbook and media fields will be imported.'
                    )

                package_version = manifest.get('version')
                if package_version not in (None, PACKAGE_FORMAT_VERSION):
                    manifest_warnings.append(
                        f'Package format version {package_version} differs from supported version '
                        f'{PACKAGE_FORMAT_VERSION}; unsupported fields may be ignored.'
                    )

                portability = manifest.get('portability')
                omitted_data = portability.get('omitted_data', []) if isinstance(portability, dict) else []
                if isinstance(omitted_data, list) and omitted_data:
                    readable_omissions = [item.strip() for item in omitted_data if isinstance(item, str) and item.strip()]
                    if readable_omissions:
                        manifest_warnings.append(
                            'Portability notice — this package does not contain: '
                            + '; '.join(readable_omissions)
                            + '.'
                        )
            staging_root = _get_package_staging_root()

            _attach_package_asset_metadata(
                parsed.get('daily', []),
                entry_type='daily',
                manifest_assets=manifest_assets,
                zip_file=zip_file,
                staging_root=staging_root,
                warnings=manifest_warnings,
            )
            _attach_package_asset_metadata(
                parsed.get('dreams', []),
                entry_type='dream',
                manifest_assets=manifest_assets,
                zip_file=zip_file,
                staging_root=staging_root,
                warnings=manifest_warnings,
            )
            _attach_package_asset_metadata(
                parsed.get('important_days', []),
                entry_type='important day',
                manifest_assets=manifest_assets,
                zip_file=zip_file,
                staging_root=staging_root,
                warnings=manifest_warnings,
            )

            parsed['package_staging_root'] = staging_root
            return parsed
    except zipfile.BadZipFile as exc:
        raise ValueError(f'Could not open zip package: {exc}') from exc


def parse_excel_workbook(file_bytes: bytes) -> dict:
    """Parse a workbook into normalised daily/dream row dictionaries."""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            'pandas is required for Excel import. '
            'Install it with: pip install pandas openpyxl'
        )

    warnings: list[str] = []
    errors: list[str] = []
    daily_rows: list[dict] = []
    dream_rows: list[dict] = []
    important_day_rows: list[dict] = []
    thought_record_rows: list[dict] = []

    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')
    except Exception as exc:
        raise ValueError(f'Could not open Excel file: {exc}') from exc

    # Build a case-insensitive sheet name map
    sheet_map = {name.strip().lower(): name for name in xls.sheet_names}

    # --- Daily sheet ---
    if 'daily' in sheet_map:
        df = pd.read_excel(xls, sheet_name=sheet_map['daily'], dtype=str)
        df.columns = _normalise_headers(df.columns)
        daily_header_errors = _validate_daily_headers_strict(df.columns.tolist())
        if daily_header_errors:
            errors.extend(daily_header_errors)
        else:
            for idx, row in df.iterrows():
                row_num = idx + 2  # Excel row number (1-indexed header + data)
                entry_date = _parse_date(row.get('date', ''))
                if not entry_date:
                    warnings.append(
                        f'Daily sheet row {row_num}: skipped — invalid or missing date '
                        f'("{row.get("date", "")}").'
                    )
                    continue
                entry_time = _parse_time(
                    row.get('entry_time', ''),
                    default=_DEFAULT_IMPORT_TIMES['daily'],
                )
                if not entry_time:
                    warnings.append(
                        f'Daily sheet row {row_num}: skipped — invalid time '
                        f'("{row.get("entry_time", "")}"). Use HH:MM.'
                    )
                    continue

                daily_rows.append({
                    'entry_date': entry_date,
                    'entry_time': entry_time,
                    'title': _sanitise(row.get('title', '')),
                    'user_message': _sanitise(row.get('user_entry', row.get('user_message', ''))),
                    'ai_response': _sanitise(row.get('ai_response', '')),
                    'entry_asset_ref': _sanitise(row.get('entry_asset_ref', '')),
                })
    else:
        warnings.append("No 'Daily' sheet found; daily entries not imported.")

    # --- Dreams sheet ---
    dream_sheet_key = next(
        (k for k in sheet_map if k in ('dreams', 'dream')), None
    )
    if dream_sheet_key:
        df = pd.read_excel(xls, sheet_name=sheet_map[dream_sheet_key], dtype=str)
        df.columns = _normalise_headers(df.columns)
        warnings.extend(
            _validate_sheet_headers(
                'Dreams',
                df.columns.tolist(),
                _DREAM_REQUIRED_HEADERS,
                ('entry_time', 'entry_asset_ref'),
            )
        )
        for idx, row in df.iterrows():
            row_num = idx + 2
            entry_date = _parse_date(row.get('date', ''))
            if not entry_date:
                warnings.append(
                    f'Dreams sheet row {row_num}: skipped — invalid or missing date '
                    f'("{row.get("date", "")}").'
                )
                continue
            
            entry_time = _parse_time(
                row.get('entry_time', ''),
                default=_DEFAULT_IMPORT_TIMES['dream'],
            )
            if not entry_time:
                warnings.append(
                    f'Dreams sheet row {row_num}: skipped — invalid time '
                    f'("{row.get("entry_time", "")}"). Use HH:MM.'
                )
                continue

            # Build row data with sanitised values
            row_data = {
                'entry_date': entry_date,
                'entry_time': entry_time,
                'title': _sanitise(row.get('title', '')),
                'plot': _sanitise(row.get('plot', '')),
                'cast': _sanitise(row.get('cast', '')),
                'location': _sanitise(row.get('location', '')),
                'period': _sanitise(row.get('period', '')),
                'emotion': _sanitise(row.get('emotion', '')),
                'symbols_and_imagery': _sanitise(row.get('symbols_and_imagery', '')),
                'insight': _sanitise(row.get('insight', '')),
                'action': _sanitise(row.get('action', '')),
                'other': _sanitise(row.get('other', '')),
                'tags': _sanitise(row.get('tags', '')),
                'entry_asset_ref': _sanitise(row.get('entry_asset_ref', '')),
            }
            
            # Derive NLTK enrichment for dreams
            enriched = _derive_dream_nltk_fields(row_data)
            row_data.update(enriched)
            
            dream_rows.append(row_data)
    else:
        warnings.append("No 'Dreams' sheet found; dream entries not imported.")

    important_day_sheet_key = next(
        (k for k in sheet_map if k in ('important days', 'important_days')), None
    )
    if important_day_sheet_key:
        df = pd.read_excel(xls, sheet_name=sheet_map[important_day_sheet_key], dtype=str)
        df.columns = _normalise_headers(df.columns)
        warnings.extend(
            _validate_sheet_headers(
                'Important Days',
                df.columns.tolist(),
                ('starts_on', 'label'),
                tuple(header for header in IMPORTANT_DAY_IMPORT_HEADERS if header not in {'starts_on', 'label'}),
            )
        )
        for idx, row in df.iterrows():
            row_num = idx + 2
            starts_on = _parse_date(row.get('starts_on', ''))
            if not starts_on:
                warnings.append(
                    f'Important Days sheet row {row_num}: skipped — invalid or missing starts_on '
                    f'("{row.get("starts_on", "")}").'
                )
                continue
            label = _sanitise(row.get('label', ''))[:60].strip()
            if not label:
                warnings.append(f'Important Days sheet row {row_num}: skipped — missing label.')
                continue
            parsed_date = datetime.strptime(starts_on, '%Y-%m-%d')
            important_day_rows.append({
                'starts_on': starts_on,
                'month': parsed_date.month,
                'day': parsed_date.day,
                'original_year': parsed_date.year,
                'label': label,
                'category': _coerce_allowed_cell(
                    row.get('category', ''),
                    {'birthday', 'anniversary', 'milestone', 'other'},
                    'other',
                ),
                'recurrence': _coerce_allowed_cell(row.get('recurrence', ''), {'once', 'yearly'}, 'yearly'),
                'icon_name': _coerce_allowed_cell(
                    row.get('icon_name', ''),
                    {
                        'cake',
                        'favorite',
                        'flag',
                        'event',
                        'celebration',
                        'star',
                        'sentiment_neutral',
                        'sentiment_dissatisfied',
                        'mood_bad',
                    },
                    'event',
                ),
                'accent_color': _coerce_allowed_cell(
                    row.get('accent_color', ''),
                    {'amber', 'rose', 'blue', 'violet', 'emerald', 'slate'},
                    'amber',
                ),
                'note': _sanitise(row.get('note', ''))[:160],
                'entry_asset_ref': _sanitise(row.get('entry_asset_ref', '')),
            })

    thought_record_sheet_key = next(
        (k for k in sheet_map if k in ('thought records', 'thought_records')), None
    )
    if thought_record_sheet_key:
        df = pd.read_excel(xls, sheet_name=sheet_map[thought_record_sheet_key], dtype=str)
        df.columns = _normalise_headers(df.columns)
        warnings.extend(
            _validate_sheet_headers(
                'Thought Records',
                df.columns.tolist(),
                ('record_date', 'title'),
                tuple(header for header in THOUGHT_RECORD_IMPORT_HEADERS if header not in {'record_date', 'title'}),
            )
        )
        for idx, row in df.iterrows():
            row_num = idx + 2
            record_date = _parse_date(row.get('record_date', ''))
            if not record_date:
                warnings.append(
                    f'Thought Records sheet row {row_num}: skipped — invalid or missing record_date '
                    f'("{row.get("record_date", "")}").'
                )
                continue
            title = _sanitise(row.get('title', ''))[:100].strip()
            if not title:
                title = 'Thought record'
            status = _coerce_allowed_cell(row.get('status', ''), {'draft', 'completed'}, 'draft')
            current_step = _coerce_int_cell(row.get('current_step', ''), default=7 if status == 'completed' else 1, minimum=1, maximum=7)
            thought_record_rows.append({
                'record_date': record_date,
                'title': title,
                'status': status,
                'current_step': current_step,
                'linked_entry_type': _coerce_allowed_cell(row.get('linked_entry_type', ''), {'daily', 'dream'}, ''),
                'linked_entry_id': _coerce_int_cell(row.get('linked_entry_id', ''), default=0, minimum=0),
                'situation': _sanitise(row.get('situation', ''))[:6000],
                'feelings_before_json': _json_cell(_parse_json_array(row.get('feelings_before', ''))),
                'unhelpful_thoughts': _sanitise(row.get('unhelpful_thoughts', ''))[:6000],
                'evidence_for': _sanitise(row.get('evidence_for', ''))[:6000],
                'evidence_against': _sanitise(row.get('evidence_against', ''))[:6000],
                'balanced_thought': _sanitise(row.get('balanced_thought', ''))[:6000],
                'feelings_after_json': _json_cell(_parse_json_array(row.get('feelings_after', ''))),
                'next_step': _sanitise(row.get('next_step', ''))[:6000],
                'ai_response': _sanitise(row.get('ai_response', ''))[:6000],
                'ai_responded_at': _sanitise(row.get('ai_responded_at', '')),
                'ai_response_outdated': _parse_boolish_cell(row.get('ai_response_outdated', '')),
            })

    return {
        'daily': daily_rows,
        'dreams': dream_rows,
        'important_days': important_day_rows,
        'thought_records': thought_record_rows,
        'errors': errors,
        'warnings': warnings,
    }


# ---------------------------------------------------------------------------
# Database insertion with duplicate detection
# ---------------------------------------------------------------------------

def insert_entries(
    conn: sqlite3.Connection,
    user_id: int,
    parsed: dict,
    import_id: int | None = None,
) -> dict:
    """
    Insert parsed entries, skipping duplicates when the same entry type,
    same date/time, normalised title, and content already exist for the user.

    Returns:
        {
          'inserted_daily':   int,
          'skipped_daily':    int,
          'inserted_dreams':  int,
          'skipped_dreams':   int,
          'duplicate_dates_daily':  [str, ...],
          'duplicate_dates_dreams': [str, ...],
          'duplicate_entries': [dict, ...],
        }
    """
    cursor = conn.cursor()

    # Fetch existing duplicate identities upfront to minimise round-trips.
    existing_daily = {
        (
            row[0],
            _normalise_time_key(row[1], entry_type='daily'),
            _normalise_title_key(row[2] or ''),
            _normalise_content_key(row[3] or ''),
        )
        for row in cursor.execute(
            'SELECT entry_date, entry_time, title, user_message '
            'FROM dailydiary_entries WHERE user_id = ?',
            (user_id,),
        )
        if _normalise_title_key(row[2] or '') and _normalise_content_key(row[3] or '')
    }
    existing_dreams = {
        (
            row[0],
            _normalise_time_key(row[1], entry_type='dream'),
            _normalise_title_key(row[2] or ''),
            _normalise_content_key(row[3] or ''),
        )
        for row in cursor.execute(
            'SELECT entry_date, entry_time, title, plot '
            'FROM dreamdiary_entries WHERE user_id = ?',
            (user_id,),
        )
        if _normalise_title_key(row[2] or '') and _normalise_content_key(row[3] or '')
    }

    inserted_daily = 0
    skipped_daily = 0
    dup_daily: list[str] = []
    duplicate_entries: list[dict[str, str]] = []

    for row in parsed.get('daily', []):
        entry_date = row['entry_date']
        entry_time = _normalise_time_key(row.get('entry_time', ''), entry_type='daily')
        title_key = _normalise_title_key(row['title'])
        content_key = _normalise_content_key(row['user_message'])
        duplicate_key = (entry_date, entry_time, title_key, content_key)
        if title_key and content_key and duplicate_key in existing_daily:
            skipped_daily += 1
            dup_daily.append(entry_date)
            duplicate_entries.append({
                'entry_type': 'daily',
                'entry_date': entry_date,
                'title': row['title'] or 'Untitled daily entry',
                'reason': 'same_date_time_title_content',
                'content_preview': _truncate_preview(row['user_message']),
                'prefill': {
                    'entry_type': 'daily',
                    'entry_date': entry_date,
                    'title': row['title'] or '',
                    'user_message': row['user_message'] or '',
                    'tags': row.get('tags', '') or '',
                },
            })
            continue

        derived_fields = _derive_daily_nltk_fields(
            row['title'],
            row['user_message'],
            source_app=row.get('source_app', ''),
        )
        ai_response = _sanitise(row.get('ai_response', ''))

        # Determine next entry_number for this date
        max_num = cursor.execute(
            'SELECT MAX(entry_number) AS max_entry_number FROM dailydiary_entries '
            'WHERE user_id = ? AND entry_date = ?',
            (user_id, entry_date),
        ).fetchone()
        max_num = _row_value(max_num, 0, 'max_entry_number') or 0

        cursor.execute(
            '''INSERT INTO dailydiary_entries
               (user_id, import_id, entry_date, entry_time, entry_number, title, user_message,
                ai_response, daily_people_names, daily_places, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                import_id,
                entry_date,
                entry_time,
                max_num + 1,
                row['title'],
                row['user_message'],
                ai_response,
                derived_fields['daily_people_names'],
                derived_fields['daily_places'],
                derived_fields['tags'],
            ),
        )
        if title_key and content_key:
            existing_daily.add(duplicate_key)
        inserted_daily += 1

    inserted_dreams = 0
    skipped_dreams = 0
    dup_dreams: list[str] = []

    for row in parsed.get('dreams', []):
        entry_date = row['entry_date']
        entry_time = _normalise_time_key(row.get('entry_time', ''), entry_type='dream')
        title_key = _normalise_title_key(row['title'])
        content_key = _normalise_content_key(row['plot'])
        duplicate_key = (entry_date, entry_time, title_key, content_key)
        if title_key and content_key and duplicate_key in existing_dreams:
            skipped_dreams += 1
            dup_dreams.append(entry_date)
            duplicate_entries.append({
                'entry_type': 'dream',
                'entry_date': entry_date,
                'title': row['title'] or 'Untitled dream entry',
                'reason': 'same_date_time_title_content',
                'content_preview': _truncate_preview(row['plot']),
                'prefill': {
                    'entry_type': 'dream',
                    'entry_date': entry_date,
                    'title': row['title'] or '',
                    'plot': row.get('plot', '') or '',
                    'cast': row.get('cast', '') or '',
                    'location': row.get('location', '') or '',
                    'period': row.get('period', '') or '',
                    'emotion': row.get('emotion', '') or '',
                    'symbols_and_imagery': row.get('symbols_and_imagery', '') or '',
                    'insight': row.get('insight', '') or '',
                    'action': row.get('action', '') or '',
                    'other': row.get('other', '') or '',
                    'tags': row.get('tags', '') or '',
                    'dream_people_names': row.get('dream_people_names', '') or '',
                    'dream_places': row.get('dream_places', '') or '',
                },
            })
            continue

        max_num = cursor.execute(
            'SELECT MAX(entry_number) AS max_entry_number FROM dreamdiary_entries '
            'WHERE user_id = ? AND entry_date = ?',
            (user_id, entry_date),
        ).fetchone()
        max_num = _row_value(max_num, 0, 'max_entry_number') or 0

        cursor.execute(
            '''INSERT INTO dreamdiary_entries
               (user_id, import_id, entry_date, entry_time, entry_number, title, "cast", location,
                period, emotion, plot, symbols_and_imagery, insight, action, other,
                tags, dream_people_names, dream_places)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                import_id,
                entry_date,
                entry_time,
                max_num + 1,
                row['title'],
                row['cast'],
                row['location'],
                row['period'],
                row['emotion'],
                row['plot'],
                row['symbols_and_imagery'],
                row['insight'],
                row['action'],
                row['other'],
                row['tags'],
                row.get('dream_people_names', ''),
                row.get('dream_places', ''),
            ),
        )
        if title_key and content_key:
            existing_dreams.add(duplicate_key)
        inserted_dreams += 1

    conn.commit()

    return {
        'inserted_daily': inserted_daily,
        'skipped_daily': skipped_daily,
        'inserted_dreams': inserted_dreams,
        'skipped_dreams': skipped_dreams,
        'duplicate_dates_daily': dup_daily,
        'duplicate_dates_dreams': dup_dreams,
        'duplicate_entries': duplicate_entries,
    }


def _fetch_existing_duplicate_keys(
    cursor: sqlite3.Cursor,
    user_id: int,
) -> tuple[set[tuple[str, str, str, str]], set[tuple[str, str, str, str]]]:
    existing_daily = {
        (
            _row_value(row, 0, 'entry_date'),
            _normalise_time_key(_row_value(row, 1, 'entry_time'), entry_type='daily'),
            _normalise_title_key(_row_value(row, 2, 'title') or ''),
            _normalise_content_key(_row_value(row, 3, 'user_message') or ''),
        )
        for row in cursor.execute(
            'SELECT entry_date, entry_time, title, user_message '
            'FROM dailydiary_entries WHERE user_id = ?',
            (user_id,),
        )
        if _normalise_title_key(_row_value(row, 2, 'title') or '')
        and _normalise_content_key(_row_value(row, 3, 'user_message') or '')
    }
    existing_dreams = {
        (
            _row_value(row, 0, 'entry_date'),
            _normalise_time_key(_row_value(row, 1, 'entry_time'), entry_type='dream'),
            _normalise_title_key(_row_value(row, 2, 'title') or ''),
            _normalise_content_key(_row_value(row, 3, 'plot') or ''),
        )
        for row in cursor.execute(
            'SELECT entry_date, entry_time, title, plot '
            'FROM dreamdiary_entries WHERE user_id = ?',
            (user_id,),
        )
        if _normalise_title_key(_row_value(row, 2, 'title') or '')
        and _normalise_content_key(_row_value(row, 3, 'plot') or '')
    }
    return existing_daily, existing_dreams


def preview_import_entries(conn: sqlite3.Connection, user_id: int, parsed: dict) -> dict:
    """Classify parsed rows into ready rows and duplicate candidates without inserting."""
    cursor = conn.cursor()
    existing_daily, existing_dreams = _fetch_existing_duplicate_keys(cursor, user_id)

    ready_daily_rows: list[dict[str, str]] = []
    ready_dream_rows: list[dict[str, str]] = []
    ready_important_day_rows: list[dict[str, str]] = []
    ready_thought_record_rows: list[dict[str, str]] = []
    duplicate_rows: list[dict[str, object]] = []
    duplicate_dates_daily: list[str] = []
    duplicate_dates_dreams: list[str] = []
    duplicate_daily_count = 0
    duplicate_dream_count = 0

    daily_duplicate_index = 0
    for source_index, row in enumerate(parsed.get('daily', []), start=1):
        review_row_id = f'daily-{source_index}'
        entry_date = row['entry_date']
        entry_time = _normalise_time_key(row.get('entry_time', ''), entry_type='daily')
        title_key = _normalise_title_key(row['title'])
        content_key = _normalise_content_key(row['user_message'])
        duplicate_key = (entry_date, entry_time, title_key, content_key)

        if title_key and content_key and duplicate_key in existing_daily:
            daily_duplicate_index += 1
            duplicate_daily_count += 1
            duplicate_dates_daily.append(entry_date)
            duplicate_rows.append({
                'row_id': review_row_id,
                'entry_type': 'daily',
                'entry_date': entry_date,
                'title': row['title'] or 'Untitled daily entry',
                'reason': 'same_date_time_title_content',
                'content_preview': _truncate_preview(row['user_message']),
                'row_data': dict(row),
            })
            continue

        ready_row = dict(row)
        ready_row['_review_row_id'] = review_row_id
        ready_daily_rows.append(ready_row)
        if title_key and content_key:
            existing_daily.add(duplicate_key)

    dream_duplicate_index = 0
    for source_index, row in enumerate(parsed.get('dreams', []), start=1):
        review_row_id = f'dream-{source_index}'
        entry_date = row['entry_date']
        entry_time = _normalise_time_key(row.get('entry_time', ''), entry_type='dream')
        title_key = _normalise_title_key(row['title'])
        content_key = _normalise_content_key(row['plot'])
        duplicate_key = (entry_date, entry_time, title_key, content_key)

        if title_key and content_key and duplicate_key in existing_dreams:
            dream_duplicate_index += 1
            duplicate_dream_count += 1
            duplicate_dates_dreams.append(entry_date)
            duplicate_rows.append({
                'row_id': review_row_id,
                'entry_type': 'dream',
                'entry_date': entry_date,
                'title': row['title'] or 'Untitled dream entry',
                'reason': 'same_date_time_title_content',
                'content_preview': _truncate_preview(row['plot']),
                'row_data': dict(row),
            })
            continue

        ready_row = dict(row)
        ready_row['_review_row_id'] = review_row_id
        ready_dream_rows.append(ready_row)
        if title_key and content_key:
            existing_dreams.add(duplicate_key)

    for source_index, row in enumerate(parsed.get('important_days', []), start=1):
        ready_row = dict(row)
        ready_row['_review_row_id'] = f'important-day-{source_index}'
        ready_important_day_rows.append(ready_row)

    for source_index, row in enumerate(parsed.get('thought_records', []), start=1):
        ready_row = dict(row)
        ready_row['_review_row_id'] = f'thought-record-{source_index}'
        ready_thought_record_rows.append(ready_row)

    preview = {
        'ready_daily_rows': ready_daily_rows,
        'ready_dream_rows': ready_dream_rows,
        'ready_important_day_rows': ready_important_day_rows,
        'ready_thought_record_rows': ready_thought_record_rows,
        'duplicate_rows': duplicate_rows,
        'summary': {
            'ready_daily': len(ready_daily_rows),
            'ready_dreams': len(ready_dream_rows),
            'ready_important_days': len(ready_important_day_rows),
            'ready_thought_records': len(ready_thought_record_rows),
            'duplicate_daily': duplicate_daily_count,
            'duplicate_dreams': duplicate_dream_count,
            'duplicate_dates_daily': duplicate_dates_daily,
            'duplicate_dates_dreams': duplicate_dates_dreams,
        },
    }
    staging_root = str(parsed.get('package_staging_root') or '').strip()
    if staging_root:
        preview['package_staging_root'] = staging_root
    return preview


def _merge_tags(*tag_groups: str) -> str:
    seen: set[str] = set()
    merged: list[str] = []

    for tag_group in tag_groups:
        for raw_tag in (tag_group or '').split(','):
            tag = raw_tag.strip()
            if not tag:
                continue
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(tag)

    return ','.join(merged)


def _cleanup_import_package_staging(preview_payload: dict) -> None:
    staging_root = str(preview_payload.get('package_staging_root') or '').strip()
    if not staging_root:
        return
    shutil.rmtree(staging_root, ignore_errors=True)


def _normalise_position_value(value: str, *, default: str = '50') -> str:
    text = str(value or '').strip()
    if not text:
        return default
    try:
        numeric = float(text)
    except ValueError:
        return default
    return str(max(0.0, min(100.0, numeric))).rstrip('0').rstrip('.') or default


def _attach_imported_media_to_entry(
    cursor: sqlite3.Cursor,
    *,
    table_name: str,
    entry_id: int,
    user_id: int,
    entry_kind: str,
    row: dict[str, str],
) -> None:
    import_image_path = str(row.get('import_image_path') or '').strip()
    if not import_image_path:
        return

    image_bytes = Path(import_image_path).read_bytes()
    storage_key = store_imported_image(
        image_bytes,
        user_id=user_id,
        entry_kind=entry_kind,
        filename=Path(import_image_path).name,
    )

    cursor.execute(
        f'''UPDATE {table_name}
            SET image_storage_key = ?,
                image_url = NULL,
                image_prompt = ?,
                recycled_image_prompt = ?,
                image_position_x = ?,
                image_position_y = ?,
                image_source = ?
            WHERE id = ? AND user_id = ?''',
        (
            storage_key,
            row.get('image_prompt') or None,
            row.get('recycled_image_prompt') or None,
            _normalise_position_value(row.get('image_position_x', '50')),
            _normalise_position_value(row.get('image_position_y', '50')),
            (row.get('image_source') or 'upload').strip() or 'upload',
            entry_id,
            user_id,
        ),
    )


def _attach_imported_media_to_important_day(
    cursor: sqlite3.Cursor,
    *,
    important_day_id: int,
    user_id: int,
    row: dict[str, str],
) -> None:
    import_image_path = str(row.get('import_image_path') or '').strip()
    if not import_image_path:
        return

    image_bytes = Path(import_image_path).read_bytes()
    storage_key = store_imported_image(
        image_bytes,
        user_id=user_id,
        entry_kind='important-day',
        filename=Path(import_image_path).name,
    )
    cursor.execute(
        '''UPDATE important_days
           SET image_storage_key = ?, image_url = NULL, updated_at = CURRENT_TIMESTAMP
           WHERE id = ? AND user_id = ?''',
        (storage_key, important_day_id, user_id),
    )


def _attach_imported_entry_assets_to_entry(
    cursor: sqlite3.Cursor,
    *,
    entry_id: int,
    user_id: int,
    entry_kind: str,
    row: dict[str, str],
) -> None:
    attachment_items = row.get('import_attachment_files', [])
    if not isinstance(attachment_items, list):
        return

    for attachment_meta in attachment_items:
        if not isinstance(attachment_meta, dict):
            continue

        staged_path = str(attachment_meta.get('staged_path') or '').strip()
        if not staged_path:
            continue

        file_bytes = Path(staged_path).read_bytes()
        original_filename = str(attachment_meta.get('original_filename') or '').strip() or Path(staged_path).name
        storage_key = store_entry_asset(
            file_bytes,
            user_id=user_id,
            entry_kind=entry_kind,
            filename=original_filename,
        )
        cursor.execute(
            '''INSERT INTO entry_assets
               (user_id, entry_type, entry_id, asset_role, storage_key, original_filename,
                mime_type, file_size_bytes, sort_order, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                entry_kind,
                entry_id,
                str(attachment_meta.get('asset_role') or 'attachment').strip() or 'attachment',
                storage_key,
                original_filename,
                str(attachment_meta.get('mime_type') or '').strip().lower(),
                int(attachment_meta.get('file_size_bytes', 0) or 0),
                int(attachment_meta.get('sort_order', 0) or 0),
                datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            ),
    )


def _insert_important_day_import_row(
    cursor: sqlite3.Cursor,
    user_id: int,
    row: dict[str, str],
) -> None:
    cursor.execute(
        append_returning_id(
            '''INSERT INTO important_days (
               user_id, label, starts_on, month, day, original_year, category,
               recurrence, icon_name, accent_color, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            _cursor_provider(cursor),
        ),
        (
            user_id,
            row['label'],
            row['starts_on'],
            row['month'],
            row['day'],
            row['original_year'],
            row['category'],
            row['recurrence'],
            row['icon_name'],
            row['accent_color'],
            row.get('note', ''),
        ),
    )
    important_day_id = inserted_id(cursor, _cursor_provider(cursor))
    _attach_imported_media_to_important_day(
        cursor,
        important_day_id=important_day_id,
        user_id=user_id,
        row=row,
    )


def _insert_thought_record_import_row(
    cursor: sqlite3.Cursor,
    user_id: int,
    row: dict[str, str],
) -> None:
    status = row.get('status') or 'draft'
    completed_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ') if status == 'completed' else None
    cursor.execute(
        append_returning_id(
            '''INSERT INTO cbt_worksheets (
               user_id, worksheet_type, title, status, current_step, record_date,
               linked_entry_type, linked_entry_id, completed_at
            ) VALUES (?, 'thought_record', ?, ?, ?, ?, NULL, NULL, ?)''',
            _cursor_provider(cursor),
        ),
        (
            user_id,
            row['title'],
            status,
            row.get('current_step', 7 if status == 'completed' else 1),
            row['record_date'],
            completed_at,
        ),
    )
    worksheet_id = inserted_id(cursor, _cursor_provider(cursor))
    cursor.execute(
        '''INSERT INTO cbt_thought_record_data (
           worksheet_id, situation, feelings_before_json, unhelpful_thoughts,
           evidence_for, evidence_against, balanced_thought, feelings_after_json,
           next_step, ai_response, ai_responded_at, ai_response_outdated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            worksheet_id,
            row.get('situation', ''),
            row.get('feelings_before_json', '[]'),
            row.get('unhelpful_thoughts', ''),
            row.get('evidence_for', ''),
            row.get('evidence_against', ''),
            row.get('balanced_thought', ''),
            row.get('feelings_after_json', '[]'),
            row.get('next_step', ''),
            row.get('ai_response', ''),
            row.get('ai_responded_at') or None,
            int(row.get('ai_response_outdated', 0) or 0),
        ),
    )


def _insert_daily_import_row(
    cursor: sqlite3.Cursor,
    user_id: int,
    row: dict[str, str],
    *,
    import_id: int,
    mark_duplicate: bool = False,
) -> None:
    entry_date = row['entry_date']
    derived_fields = _derive_daily_nltk_fields(
        row['title'],
        row['user_message'],
        source_app=row.get('source_app', ''),
    )
    ai_response = _sanitise(row.get('ai_response', ''))
    max_num = cursor.execute(
        'SELECT MAX(entry_number) AS max_entry_number FROM dailydiary_entries WHERE user_id = ? AND entry_date = ?',
        (user_id, entry_date),
    ).fetchone()
    max_num = _row_value(max_num, 0, 'max_entry_number') or 0

    tags = _merge_tags(
        row.get('tags', '') or '',
        derived_fields['tags'],
        _DUPLICATE_TAG if mark_duplicate else '',
    )

    cursor.execute(
        append_returning_id(
            '''INSERT INTO dailydiary_entries
           (user_id, import_id, entry_date, entry_time, entry_number, title, user_message,
            ai_response, daily_people_names, daily_places, tags, mood)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            _cursor_provider(cursor),
        ),
        (
            user_id,
            import_id,
            entry_date,
            row.get('entry_time', _DEFAULT_IMPORT_TIMES['daily']),
            max_num + 1,
            row['title'],
            row['user_message'],
            ai_response,
            derived_fields['daily_people_names'],
            derived_fields['daily_places'],
            tags,
            row.get('mood', ''),
        ),
    )
    entry_id = inserted_id(cursor, _cursor_provider(cursor))
    _attach_imported_media_to_entry(
        cursor,
        table_name='dailydiary_entries',
        entry_id=entry_id,
        user_id=user_id,
        entry_kind='daily',
        row=row,
    )
    _attach_imported_entry_assets_to_entry(
        cursor,
        entry_id=entry_id,
        user_id=user_id,
        entry_kind='daily',
        row=row,
    )


def _insert_dream_import_row(
    cursor: sqlite3.Cursor,
    user_id: int,
    row: dict[str, str],
    *,
    import_id: int,
    mark_duplicate: bool = False,
) -> None:
    entry_date = row['entry_date']
    max_num = cursor.execute(
        'SELECT MAX(entry_number) AS max_entry_number FROM dreamdiary_entries WHERE user_id = ? AND entry_date = ?',
        (user_id, entry_date),
    ).fetchone()
    max_num = _row_value(max_num, 0, 'max_entry_number') or 0
    tags = _merge_tags(row.get('tags', '') or '', _DUPLICATE_TAG if mark_duplicate else '')

    cursor.execute(
        append_returning_id(
            '''INSERT INTO dreamdiary_entries
           (user_id, import_id, entry_date, entry_time, entry_number, title, "cast", location,
            period, emotion, plot, symbols_and_imagery, insight, action, other,
            tags, dream_people_names, dream_places)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            _cursor_provider(cursor),
        ),
        (
            user_id,
            import_id,
            entry_date,
            row.get('entry_time', _DEFAULT_IMPORT_TIMES['dream']),
            max_num + 1,
            row['title'],
            row['cast'],
            row['location'],
            row['period'],
            row['emotion'],
            row['plot'],
            row['symbols_and_imagery'],
            row['insight'],
            row['action'],
            row['other'],
            tags,
            row.get('dream_people_names', ''),
            row.get('dream_places', ''),
        ),
    )
    entry_id = inserted_id(cursor, _cursor_provider(cursor))
    _attach_imported_media_to_entry(
        cursor,
        table_name='dreamdiary_entries',
        entry_id=entry_id,
        user_id=user_id,
        entry_kind='dream',
        row=row,
    )
    _attach_imported_entry_assets_to_entry(
        cursor,
        entry_id=entry_id,
        user_id=user_id,
        entry_kind='dream',
        row=row,
    )


def commit_import_preview(
    conn: sqlite3.Connection,
    user_id: int,
    preview_payload: dict,
    import_id: int,
    accepted_duplicate_row_ids: set[str] | None = None,
    selected_row_ids: set[str] | None = None,
    entry_type_overrides: dict[str, str] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict:
    """Commit a staged import preview, optionally including accepted duplicates."""
    accepted_duplicate_row_ids = accepted_duplicate_row_ids or set()
    entry_type_overrides = entry_type_overrides or {}
    cursor = conn.cursor()

    inserted_daily = 0
    inserted_dreams = 0
    inserted_important_days = 0
    inserted_thought_records = 0
    accepted_duplicate_daily = 0
    accepted_duplicate_dreams = 0
    ready_daily_rows = [
        row for row in preview_payload.get('ready_daily_rows', [])
        if selected_row_ids is None or row.get('_review_row_id') in selected_row_ids
    ]
    ready_dream_rows = [
        row for row in preview_payload.get('ready_dream_rows', [])
        if selected_row_ids is None or row.get('_review_row_id') in selected_row_ids
    ]
    ready_important_day_rows = [
        row for row in preview_payload.get('ready_important_day_rows', [])
        if selected_row_ids is None or row.get('_review_row_id') in selected_row_ids
    ]
    ready_thought_record_rows = [
        row for row in preview_payload.get('ready_thought_record_rows', [])
        if selected_row_ids is None or row.get('_review_row_id') in selected_row_ids
    ]
    duplicate_rows = [
        row for row in preview_payload.get('duplicate_rows', [])
        if (
            row.get('row_id') in selected_row_ids
            if selected_row_ids is not None
            else row.get('row_id') in accepted_duplicate_row_ids
        )
    ]
    total_rows = (
        len(ready_daily_rows)
        + len(ready_dream_rows)
        + len(ready_important_day_rows)
        + len(ready_thought_record_rows)
        + len(duplicate_rows)
    )
    processed_rows = 0

    def report_progress() -> None:
        if progress_callback:
            progress_callback(processed_rows, total_rows)

    try:
        report_progress()
        for row in ready_daily_rows:
            if entry_type_overrides.get(row.get('_review_row_id')) == 'dream':
                _insert_dream_import_row(cursor, user_id, _daily_row_as_dream(row), import_id=import_id)
                inserted_dreams += 1
            else:
                _insert_daily_import_row(cursor, user_id, row, import_id=import_id)
                inserted_daily += 1
            processed_rows += 1
            report_progress()

        for row in ready_dream_rows:
            if entry_type_overrides.get(row.get('_review_row_id')) == 'daily':
                _insert_daily_import_row(cursor, user_id, _dream_row_as_daily(row), import_id=import_id)
                inserted_daily += 1
            else:
                _insert_dream_import_row(cursor, user_id, row, import_id=import_id)
                inserted_dreams += 1
            processed_rows += 1
            report_progress()

        for row in ready_important_day_rows:
            _insert_important_day_import_row(cursor, user_id, row)
            inserted_important_days += 1
            processed_rows += 1
            report_progress()

        for row in ready_thought_record_rows:
            _insert_thought_record_import_row(cursor, user_id, row)
            inserted_thought_records += 1
            processed_rows += 1
            report_progress()

        for duplicate in duplicate_rows:
            entry_type = duplicate.get('entry_type')
            entry_type = entry_type_overrides.get(duplicate.get('row_id'), entry_type)
            row_data = duplicate.get('row_data')
            if not isinstance(row_data, dict):
                processed_rows += 1
                report_progress()
                continue
            if entry_type == 'daily':
                if duplicate.get('entry_type') == 'dream':
                    row_data = _dream_row_as_daily(row_data)
                _insert_daily_import_row(
                    cursor,
                    user_id,
                    row_data,
                    import_id=import_id,
                    mark_duplicate=True,
                )
                inserted_daily += 1
                accepted_duplicate_daily += 1
            elif entry_type == 'dream':
                if duplicate.get('entry_type') == 'daily':
                    row_data = _daily_row_as_dream(row_data)
                _insert_dream_import_row(
                    cursor,
                    user_id,
                    row_data,
                    import_id=import_id,
                    mark_duplicate=True,
                )
                inserted_dreams += 1
                accepted_duplicate_dreams += 1
            processed_rows += 1
            report_progress()

        skipped_daily = preview_payload.get('summary', {}).get('duplicate_daily', 0) - accepted_duplicate_daily
        skipped_dreams = preview_payload.get('summary', {}).get('duplicate_dreams', 0) - accepted_duplicate_dreams
        conn.commit()

        return {
            'inserted_daily': inserted_daily,
            'skipped_daily': max(0, skipped_daily),
            'inserted_dreams': inserted_dreams,
            'skipped_dreams': max(0, skipped_dreams),
            'inserted_important_days': inserted_important_days,
            'inserted_thought_records': inserted_thought_records,
            'duplicate_dates_daily': preview_payload.get('summary', {}).get('duplicate_dates_daily', []),
            'duplicate_dates_dreams': preview_payload.get('summary', {}).get('duplicate_dates_dreams', []),
            'duplicate_entries': [],
            'accepted_duplicate_daily': accepted_duplicate_daily,
            'accepted_duplicate_dreams': accepted_duplicate_dreams,
        }
    finally:
        _cleanup_import_package_staging(preview_payload)


def _daily_row_as_dream(row: dict) -> dict:
    converted = dict(row)
    converted.update({
        'plot': row.get('user_message', ''),
        'cast': '',
        'location': '',
        'period': '',
        'emotion': row.get('mood', ''),
        'symbols_and_imagery': '',
        'insight': '',
        'action': '',
        'other': '',
        'dream_people_names': '',
        'dream_places': '',
    })
    return converted


def _dream_row_as_daily(row: dict) -> dict:
    converted = dict(row)
    converted.update({
        'user_message': row.get('plot', ''),
        'ai_response': row.get('interpretation', ''),
        'mood': row.get('emotion', ''),
        'daily_people_names': '',
        'daily_places': '',
    })
    return converted


def backfill_nltk_enrichment(conn: sqlite3.Connection, logger=None) -> None:
    """Re-enrich daily and dream entries that have empty NLTK fields."""
    try:
        # Backfill daily entries
        daily_rows = conn.execute(
            '''SELECT id, title, user_message FROM dailydiary_entries
               WHERE (tags IS NULL OR tags = '')
               AND (daily_people_names IS NULL OR daily_people_names = '')
               AND (daily_places IS NULL OR daily_places = '')'''
        ).fetchall()

        updated_daily = 0
        for row in daily_rows:
            derived = _derive_daily_nltk_fields(row[1] or '', row[2] or '')
            if any(derived.values()):
                conn.execute(
                    '''UPDATE dailydiary_entries
                       SET tags = ?, daily_people_names = ?, daily_places = ?
                       WHERE id = ?''',
                    (derived['tags'], derived['daily_people_names'], derived['daily_places'], row[0]),
                )
                updated_daily += 1

        # Backfill dream entries
        dream_rows = conn.execute(
            '''SELECT id, title, "cast", location, period, emotion, plot,
                      symbols_and_imagery, insight, action, other, tags
               FROM dreamdiary_entries
               WHERE (dream_people_names IS NULL OR dream_people_names = '')
               AND (dream_places IS NULL OR dream_places = '')'''
        ).fetchall()

        updated_dreams = 0
        for row in dream_rows:
            row_data = {
                'title': row[1] or '',
                'cast': row[2] or '',
                'location': row[3] or '',
                'period': row[4] or '',
                'emotion': row[5] or '',
                'plot': row[6] or '',
                'symbols_and_imagery': row[7] or '',
                'insight': row[8] or '',
                'action': row[9] or '',
                'other': row[10] or '',
                'tags': row[11] or '',
            }
            derived = _derive_dream_nltk_fields(row_data)
            if derived.get('dream_people_names') or derived.get('dream_places'):
                conn.execute(
                    '''UPDATE dreamdiary_entries
                       SET tags = ?, dream_people_names = ?, dream_places = ?
                       WHERE id = ?''',
                    (derived['tags'], derived['dream_people_names'], derived['dream_places'], row[0]),
                )
                updated_dreams += 1

        if updated_daily or updated_dreams:
            conn.commit()
            if logger:
                if updated_daily:
                    logger.info('NLTK backfill: enriched %d daily entries', updated_daily)
                if updated_dreams:
                    logger.info('NLTK backfill: enriched %d dream entries', updated_dreams)
    except Exception as exc:
        if logger:
            logger.warning('NLTK backfill skipped: %s', exc)


# ---------------------------------------------------------------------------
# Import history
# ---------------------------------------------------------------------------

IMPORT_HISTORY_DDL = '''
CREATE TABLE IF NOT EXISTS import_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    imported_at     TEXT    NOT NULL,
    filename        TEXT    NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    inserted_daily  INTEGER NOT NULL DEFAULT 0,
    skipped_daily   INTEGER NOT NULL DEFAULT 0,
    inserted_dreams INTEGER NOT NULL DEFAULT 0,
    skipped_dreams  INTEGER NOT NULL DEFAULT 0,
    warnings        TEXT,
    status          TEXT    NOT NULL DEFAULT 'success',
    FOREIGN KEY (user_id) REFERENCES users(id)
)
'''

EXPORT_HISTORY_DDL = '''
CREATE TABLE IF NOT EXISTS export_history (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL,
    exported_at           TEXT    NOT NULL,
    filename              TEXT    NOT NULL,
    from_date             TEXT,
    to_date               TEXT,
    include_daily         INTEGER NOT NULL DEFAULT 1,
    include_dreams        INTEGER NOT NULL DEFAULT 1,
    daily_count           INTEGER NOT NULL DEFAULT 0,
    dream_count           INTEGER NOT NULL DEFAULT 0,
    is_full_range         INTEGER NOT NULL DEFAULT 0,
    guard_token           TEXT,
    used_for_bulk_delete  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
'''

IMPORT_SESSIONS_DDL = '''
CREATE TABLE IF NOT EXISTS import_sessions (
    id              TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    created_at      TEXT NOT NULL,
    filename        TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    payload_json    TEXT NOT NULL,
    consumed_at     TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
'''

IMPORT_JOBS_DDL = '''
CREATE TABLE IF NOT EXISTS import_jobs (
    id                TEXT PRIMARY KEY,
    user_id           INTEGER NOT NULL,
    import_session_id TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'queued',
    processed         INTEGER NOT NULL DEFAULT 0,
    total             INTEGER NOT NULL DEFAULT 0,
    percent           INTEGER NOT NULL DEFAULT 0,
    message           TEXT NOT NULL DEFAULT '',
    error             TEXT,
    request_json      TEXT NOT NULL DEFAULT '{}',
    result_json       TEXT,
    import_id         INTEGER,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    started_at        TEXT,
    completed_at      TEXT,
    attempt_count     INTEGER NOT NULL DEFAULT 0,
    worker_token      TEXT,
    lease_expires_at  TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
'''


def _require_managed_postgres_table(conn, table_name: str) -> None:
    row = conn.execute("SELECT to_regclass(?) AS table_name", (f'public.{table_name}',)).fetchone()
    resolved_table_name = row.get('table_name') if isinstance(row, dict) else row[0]
    if resolved_table_name is None:
        raise RuntimeError(
            f'Postgres {table_name} table is missing. Run managed Postgres migrations before startup.'
        )


def ensure_history_table(conn: sqlite3.Connection) -> None:
    """Create or repair import_history table for older local databases."""
    if _connection_provider(conn) != 'sqlite':
        _require_managed_postgres_table(conn, 'import_history')
        return

    conn.execute(IMPORT_HISTORY_DDL)

    table_info_rows = table_info(conn, 'import_history')
    EXPECTED_COLUMNS = {
        'id',
        'user_id',
        'imported_at',
        'filename',
        'file_size_bytes',
        'inserted_daily',
        'skipped_daily',
        'inserted_dreams',
        'skipped_dreams',
        'warnings',
        'status',
    }

    for row in table_info_rows:
        col_name = row[1]
        if col_name in EXPECTED_COLUMNS:
            continue
        if row[3] == 1 and row[4] is None:
            conn.execute(f'ALTER TABLE import_history DROP COLUMN {col_name}')

    columns = {row[1]: row for row in table_info(conn, 'import_history')}

    if 'imported_at' not in columns:
        conn.execute("ALTER TABLE import_history ADD COLUMN imported_at TEXT")
        imported_at_fallback = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        if 'import_date' in columns:
            conn.execute(
                "UPDATE import_history SET imported_at = COALESCE(import_date, ?)",
                (imported_at_fallback,),
            )
        else:
            conn.execute(
                "UPDATE import_history SET imported_at = ?",
                (imported_at_fallback,),
            )

    # Drop the legacy 'import_date' column now that 'imported_at' exists
    if 'import_date' in columns:
        conn.execute('ALTER TABLE import_history DROP COLUMN import_date')

    if 'file_size_bytes' not in columns:
        conn.execute(
            "ALTER TABLE import_history ADD COLUMN file_size_bytes INTEGER NOT NULL DEFAULT 0"
        )

    if 'inserted_daily' not in columns:
        conn.execute(
            "ALTER TABLE import_history ADD COLUMN inserted_daily INTEGER NOT NULL DEFAULT 0"
        )

    if 'skipped_daily' not in columns:
        conn.execute(
            "ALTER TABLE import_history ADD COLUMN skipped_daily INTEGER NOT NULL DEFAULT 0"
        )

    if 'inserted_dreams' not in columns:
        conn.execute(
            "ALTER TABLE import_history ADD COLUMN inserted_dreams INTEGER NOT NULL DEFAULT 0"
        )

    if 'skipped_dreams' not in columns:
        conn.execute(
            "ALTER TABLE import_history ADD COLUMN skipped_dreams INTEGER NOT NULL DEFAULT 0"
        )

    if 'warnings' not in columns:
        conn.execute("ALTER TABLE import_history ADD COLUMN warnings TEXT")

    if 'status' not in columns:
        conn.execute(
            "ALTER TABLE import_history ADD COLUMN status TEXT NOT NULL DEFAULT 'success'"
        )

    conn.commit()


def ensure_export_history_table(conn: sqlite3.Connection) -> None:
    """Create or repair export_history table for guarded bulk-delete flow."""
    if _connection_provider(conn) != 'sqlite':
        _require_managed_postgres_table(conn, 'export_history')
        return

    conn.execute(EXPORT_HISTORY_DDL)

    columns = {row[1]: row for row in table_info(conn, 'export_history')}

    required_columns = {
        'exported_at': "TEXT NOT NULL DEFAULT ''",
        'filename': "TEXT NOT NULL DEFAULT ''",
        'from_date': 'TEXT',
        'to_date': 'TEXT',
        'include_daily': 'INTEGER NOT NULL DEFAULT 1',
        'include_dreams': 'INTEGER NOT NULL DEFAULT 1',
        'daily_count': 'INTEGER NOT NULL DEFAULT 0',
        'dream_count': 'INTEGER NOT NULL DEFAULT 0',
        'is_full_range': 'INTEGER NOT NULL DEFAULT 0',
        'guard_token': 'TEXT',
        'used_for_bulk_delete': 'INTEGER NOT NULL DEFAULT 0',
    }

    for column_name, definition in required_columns.items():
        if column_name in columns:
            continue
        conn.execute(f'ALTER TABLE export_history ADD COLUMN {column_name} {definition}')

    conn.commit()


def ensure_import_sessions_table(conn: sqlite3.Connection) -> None:
    """Create or repair import_sessions table used for staged duplicate review."""
    if _connection_provider(conn) != 'sqlite':
        _require_managed_postgres_table(conn, 'import_sessions')
        return

    conn.execute(IMPORT_SESSIONS_DDL)

    columns = {row[1]: row for row in table_info(conn, 'import_sessions')}
    required_columns = {
        'created_at': "TEXT NOT NULL DEFAULT ''",
        'filename': "TEXT NOT NULL DEFAULT ''",
        'file_size_bytes': 'INTEGER NOT NULL DEFAULT 0',
        'payload_json': "TEXT NOT NULL DEFAULT '{}'",
        'consumed_at': 'TEXT',
    }

    for column_name, definition in required_columns.items():
        if column_name in columns:
            continue
        conn.execute(f'ALTER TABLE import_sessions ADD COLUMN {column_name} {definition}')

    conn.commit()


def ensure_import_jobs_table(conn: sqlite3.Connection) -> None:
    """Create or repair durable background import job storage."""
    if _connection_provider(conn) != 'sqlite':
        _require_managed_postgres_table(conn, 'import_jobs')
        return

    conn.execute(IMPORT_JOBS_DDL)
    columns = table_columns(conn, 'import_jobs')
    required_columns = {
        'processed': 'INTEGER NOT NULL DEFAULT 0',
        'total': 'INTEGER NOT NULL DEFAULT 0',
        'percent': 'INTEGER NOT NULL DEFAULT 0',
        'message': "TEXT NOT NULL DEFAULT ''",
        'error': 'TEXT',
        'request_json': "TEXT NOT NULL DEFAULT '{}'",
        'result_json': 'TEXT',
        'import_id': 'INTEGER',
        'updated_at': "TEXT NOT NULL DEFAULT ''",
        'started_at': 'TEXT',
        'completed_at': 'TEXT',
        'attempt_count': 'INTEGER NOT NULL DEFAULT 0',
        'worker_token': 'TEXT',
        'lease_expires_at': 'TEXT',
    }
    for column_name, definition in required_columns.items():
        if column_name not in columns:
            conn.execute(f'ALTER TABLE import_jobs ADD COLUMN {column_name} {definition}')
    conn.execute(
        '''CREATE INDEX IF NOT EXISTS idx_import_jobs_user_status
           ON import_jobs(user_id, status, updated_at)'''
    )
    conn.commit()


def create_import_session(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    filename: str,
    file_size: int,
    payload: dict,
) -> str:
    """Persist a short-lived staged import session and return its id."""
    ensure_import_sessions_table(conn)
    session_id = secrets.token_urlsafe(18)
    created_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    conn.execute(
        '''INSERT INTO import_sessions
           (id, user_id, created_at, filename, file_size_bytes, payload_json, consumed_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL)''',
        (
            session_id,
            user_id,
            created_at,
            filename,
            file_size,
            json.dumps(payload),
        ),
    )
    conn.commit()
    return session_id


def get_import_session(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    session_id: str,
) -> dict | None:
    """Return an active staged import session for the given user."""
    ensure_import_sessions_table(conn)
    row = conn.execute(
        '''SELECT id, user_id, created_at, filename, file_size_bytes, payload_json, consumed_at
           FROM import_sessions
           WHERE id = ? AND user_id = ? AND consumed_at IS NULL
           LIMIT 1''',
        (session_id, user_id),
    ).fetchone()
    if not row:
        return None

    record = dict(row)
    try:
        record['payload'] = json.loads(record.pop('payload_json'))
    except (TypeError, ValueError):
        record['payload'] = {}
    return record


def mark_import_session_consumed(conn: sqlite3.Connection, session_id: str) -> None:
    """Mark a staged import session as consumed so it cannot be reused."""
    conn.execute(
        'UPDATE import_sessions SET consumed_at = ? WHERE id = ?',
        (datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), session_id),
    )
    conn.commit()


def discard_import_session(conn: sqlite3.Connection, *, user_id: int, session_id: str) -> bool:
    session = get_import_session(conn, user_id=user_id, session_id=session_id)
    if not session:
        return False
    _cleanup_import_package_staging(session.get('payload', {}))
    conn.execute(
        'DELETE FROM import_sessions WHERE id = ? AND user_id = ? AND consumed_at IS NULL',
        (session_id, user_id),
    )
    conn.commit()
    return True


def record_import_history(
    conn: sqlite3.Connection,
    user_id: int,
    filename: str,
    file_size: int,
    result: dict,
    warnings: list[str],
    status: str = 'success',
) -> int:
    """Insert a row into import_history and return the new id."""
    import json

    cursor = conn.cursor()
    cursor.execute(
        append_returning_id(
            '''INSERT INTO import_history
           (user_id, imported_at, filename, file_size_bytes,
            inserted_daily, skipped_daily, inserted_dreams, skipped_dreams,
            warnings, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            _connection_provider(conn),
        ),
        (
            user_id,
            datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            filename,
            file_size,
            result.get('inserted_daily', 0),
            result.get('skipped_daily', 0),
            result.get('inserted_dreams', 0),
            result.get('skipped_dreams', 0),
            json.dumps(warnings) if warnings else None,
            status,
        ),
    )
    new_id = inserted_id(cursor, _connection_provider(conn))
    conn.commit()
    return new_id


def create_pending_import_history(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    filename: str,
    file_size: int,
) -> int:
    """Reserve an import history id before inserting entries linked to it."""
    return record_import_history(
        conn,
        user_id,
        filename,
        file_size,
        {
            'inserted_daily': 0,
            'skipped_daily': 0,
            'inserted_dreams': 0,
            'skipped_dreams': 0,
        },
        [],
        status='processing',
    )


def finalise_import_history(
    conn: sqlite3.Connection,
    *,
    import_id: int,
    user_id: int,
    result: dict,
    warnings: list[str],
    status: str,
) -> None:
    """Complete a reserved history row after its linked entries are committed."""
    conn.execute(
        '''UPDATE import_history
           SET inserted_daily = ?, skipped_daily = ?,
               inserted_dreams = ?, skipped_dreams = ?, warnings = ?, status = ?
           WHERE id = ? AND user_id = ?''',
        (
            result.get('inserted_daily', 0),
            result.get('skipped_daily', 0),
            result.get('inserted_dreams', 0),
            result.get('skipped_dreams', 0),
            json.dumps(warnings) if warnings else None,
            status,
            import_id,
            user_id,
        ),
    )
    conn.commit()


def get_import_history(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    """Return all import history rows for a user, most recent first."""
    import json

    rows = conn.execute(
        '''SELECT id, imported_at, filename, file_size_bytes,
                  inserted_daily, skipped_daily, inserted_dreams, skipped_dreams,
                  warnings, status
           FROM import_history
           WHERE user_id = ?
           ORDER BY imported_at DESC''',
        (user_id,),
    ).fetchall()

    history = []
    for row in rows:
        record = dict(row)
        raw_warnings = record.get('warnings')
        if raw_warnings:
            try:
                record['warnings'] = json.loads(raw_warnings)
            except (ValueError, TypeError):
                record['warnings'] = [raw_warnings]
        else:
            record['warnings'] = []
        history.append(record)

    return history


def record_export_history(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    filename: str,
    from_date: str | None,
    to_date: str | None,
    include_daily: bool,
    include_dreams: bool,
    daily_count: int,
    dream_count: int,
    is_full_range: bool,
    issue_guard_token: bool,
) -> dict[str, str | bool | int | None]:
    """Insert an export-history row and optionally issue a one-time guard token."""
    ensure_export_history_table(conn)
    guard_token = secrets.token_urlsafe(24) if issue_guard_token else None
    exported_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    cursor = conn.cursor()
    cursor.execute(
        append_returning_id(
            '''INSERT INTO export_history
           (user_id, exported_at, filename, from_date, to_date, include_daily,
            include_dreams, daily_count, dream_count, is_full_range, guard_token,
            used_for_bulk_delete)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)''',
            _connection_provider(conn),
        ),
        (
            user_id,
            exported_at,
            filename,
            from_date,
            to_date,
            1 if include_daily else 0,
            1 if include_dreams else 0,
            daily_count,
            dream_count,
            1 if is_full_range else 0,
            guard_token,
        ),
    )
    export_id = inserted_id(cursor, _connection_provider(conn))
    conn.commit()
    return {
        'export_id': export_id,
        'guard_token': guard_token,
        'is_full_range': is_full_range,
    }


def get_latest_bulk_delete_guard(
    conn: sqlite3.Connection,
    user_id: int,
    guard_token: str | None,
) -> dict | None:
    """Return the latest matching unused guard export record for a user."""
    if not guard_token:
        return None

    ensure_export_history_table(conn)
    row = conn.execute(
        '''SELECT id, user_id, exported_at, from_date, to_date, include_daily,
                  include_dreams, daily_count, dream_count, is_full_range,
                  guard_token, used_for_bulk_delete
           FROM export_history
           WHERE user_id = ? AND guard_token = ? AND used_for_bulk_delete = 0
           ORDER BY exported_at DESC
           LIMIT 1''',
        (user_id, guard_token),
    ).fetchone()
    return dict(row) if row else None


def mark_export_guard_used(conn: sqlite3.Connection, export_history_id: int) -> None:
    """Mark a qualifying export guard token as consumed by bulk delete."""
    conn.execute(
        'UPDATE export_history SET used_for_bulk_delete = 1 WHERE id = ?',
        (export_history_id,),
    )
    conn.commit()

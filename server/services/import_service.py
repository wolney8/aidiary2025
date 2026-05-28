# server/services/import_service.py
# Excel import service: validation, parsing, duplicate handling, history tracking
import io
import logging
import math
import re
import sqlite3
from datetime import datetime, date, timezone
from collections import Counter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {'.xlsx'}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_TYPES = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/octet-stream',  # generic binary used by some clients
}

DAILY_IMPORT_HEADERS = ('date', 'title', 'user_entry', 'ai_response')
DREAM_IMPORT_HEADERS = (
    'date',
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
)

# Script-injection patterns to strip from cell values
_INJECTION_PATTERNS = re.compile(r'[<>]|javascript:', re.IGNORECASE)
_FORMULA_PREFIXES = ('=', '+', '-', '@')


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_file(filename: str, content_type: str, file_size: int) -> list[str]:
    """Return a list of human-readable error strings; empty means valid."""
    errors: list[str] = []
    if not filename:
        errors.append('No filename provided.')
        return errors

    ext = _file_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(
            f'Invalid file type "{ext}". Only .xlsx files are accepted.'
        )

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        errors.append(
            f'Invalid content type "{content_type}". Please upload an .xlsx file.'
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


def _normalise_headers(columns) -> list[str]:
    return [str(column).strip().lower() for column in columns]


def _normalise_header_set(columns: list[str]) -> set[str]:
    return {column for column in columns if column}


def _validate_sheet_headers(
    sheet_name: str,
    columns: list[str],
    expected_headers: tuple[str, ...],
) -> list[str]:
    warnings: list[str] = []
    missing = [header for header in expected_headers if header not in columns]
    unexpected = [column for column in columns if column and column not in expected_headers]

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
    expected = set(DAILY_IMPORT_HEADERS)
    actual = _normalise_header_set(columns)
    header_counts = Counter(columns)
    duplicates = [name for name, count in header_counts.items() if name and count > 1]

    if actual == expected and not duplicates:
        return []

    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
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


def _derive_daily_nltk_fields(title: str, user_message: str) -> dict[str, str]:
    text = f'{title} {user_message}'.strip()
    if not text:
        return {
            'tags': '',
            'daily_people_names': '',
            'daily_places': '',
        }

    try:
        from nltk import ne_chunk, pos_tag, word_tokenize
        from nltk.corpus import stopwords
        from nltk.tree import Tree
    except Exception:
        return {
            'tags': '',
            'daily_people_names': '',
            'daily_places': '',
        }

    tags: list[str] = []
    people_names: list[str] = []
    places: list[str] = []

    try:
        # Load English stopwords for filtering
        try:
            stop_words = set(stopwords.words('english'))
        except LookupError:
            # If stopwords not downloaded, use a minimal set
            stop_words = set()

        # Tag blocklist - only meta words we don't want as tags
        tag_blocklist = {
            'example', 'diary', 'entry', 'daily', 'dream'
        }
        
        # Entity blocklist - for person/place name filtering
        entity_blocklist = {
            'example', 'diary', 'entry', 'daily', 'dream', 'today', 'yesterday',
            'tomorrow', 'morning', 'afternoon', 'evening', 'night', 'work',
            'home', 'day', 'week', 'month', 'year', 'time', 'project', 'good',
            'great', 'nice', 'productive', 'wonderful', 'progress', 'flying'
        }

        tokens = word_tokenize(text)
        tagged_tokens = pos_tag(tokens)
        ner_tree = ne_chunk(tagged_tokens)

        for token, pos in tagged_tokens:
            token_clean = token.strip().lower()
            if not token_clean or len(token_clean) < 3:
                continue
            if not token_clean.isalpha():
                continue
            if token_clean in stop_words or token_clean in tag_blocklist:
                continue
            if pos.startswith('NN') or pos.startswith('JJ'):
                tags.append(token_clean)

        for node in ner_tree:
            if not isinstance(node, Tree):
                continue

            label = node.label()
            entity = ' '.join(leaf[0] for leaf in node.leaves()).strip()
            if not entity:
                continue

            if label == 'PERSON':
                # Filter out obviously wrong person names
                entity_lower = entity.lower()
                entity_words = entity_lower.split()
                
                # Skip if all words are stopwords or blocklisted
                if all(word in stop_words or word in entity_blocklist for word in entity_words):
                    continue
                
                # Skip single-word "names" that are common words
                if len(entity_words) == 1 and (entity_lower in stop_words or entity_lower in entity_blocklist):
                    continue
                
                # Skip all-caps (likely acronyms, not names)
                if entity.isupper() and len(entity) > 1:
                    continue
                
                people_names.append(entity)
                tags.append(entity.lower().replace(' ', '_'))
            elif label in {'GPE', 'LOCATION', 'FACILITY'}:
                places.append(entity)
                tags.append(entity.lower().replace(' ', '_'))
    except (LookupError, ValueError, TypeError):
        return {
            'tags': '',
            'daily_people_names': '',
            'daily_places': '',
        }
    except Exception as _nltk_exc:  # noqa: BLE001
        logging.getLogger(__name__).debug('NLTK enrichment failed: %s', _nltk_exc)

    deduped_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in tags:
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        deduped_tags.append(tag)

    def _dedupe_case_insensitive(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(value)
        return ordered

    return {
        'tags': ','.join(deduped_tags[:20]),
        'daily_people_names': ','.join(_dedupe_case_insensitive(people_names)[:20]),
        'daily_places': ','.join(_dedupe_case_insensitive(places)[:20]),
    }


def _derive_dream_nltk_fields(row_data: dict[str, str]) -> dict[str, str]:
    """Extract people, places, and tags from dream entry fields using NLTK NER."""
    # Combine relevant dream fields for text analysis
    text_parts = [
        row_data.get('title', ''),
        row_data.get('plot', ''),
        row_data.get('cast', ''),
        row_data.get('symbols_and_imagery', ''),
        row_data.get('insight', ''),
        row_data.get('action', ''),
        row_data.get('other', ''),
    ]
    text = ' '.join(part for part in text_parts if part).strip()
    
    if not text:
        return {
            'tags': row_data.get('tags', ''),
            'dream_people_names': '',
            'dream_places': '',
        }

    try:
        from nltk import ne_chunk, pos_tag, word_tokenize
        from nltk.corpus import stopwords
        from nltk.tree import Tree
    except Exception:
        return {
            'tags': row_data.get('tags', ''),
            'dream_people_names': '',
            'dream_places': '',
        }

    tags: list[str] = []
    people_names: list[str] = []
    places: list[str] = []

    try:
        # Load English stopwords
        try:
            stop_words = set(stopwords.words('english'))
        except LookupError:
            stop_words = set()

        # Tag blocklist - only meta/junk words we don't want as tags
        tag_blocklist = {
            'image', 'generated', 'prompt', 'example', 'unknown',
            'dream', 'lucid', 'vivid', 'nightmare'
        }
        
        # Entity blocklist - broader list for person/place name filtering
        entity_blocklist = {
            'dream', 'flying', 'image', 'generated', 'prompt', 'lucid', 'vivid',
            'nightmare', 'sleep', 'wake', 'asleep', 'awake', 'night', 'morning',
            'example', 'unknown', 'people', 'person', 'someone', 'somebody',
            # Abstract nouns and emotions
            'freedom', 'joy', 'fear', 'love', 'hope', 'peace', 'happiness',
            'sadness', 'anger', 'excitement', 'wonder', 'surprise',
            # Common dream elements that NLTK mistakes for names
            'wings', 'clouds', 'mountains', 'ocean', 'sky', 'water', 'light',
            'darkness', 'shadow', 'time', 'space', 'world', 'life', 'death',
            # Meta words
            'present', 'past', 'future', 'day', 'week', 'month', 'year'
        }

        tokens = word_tokenize(text)
        tagged_tokens = pos_tag(tokens)
        ner_tree = ne_chunk(tagged_tokens)

        for token, pos in tagged_tokens:
            token_clean = token.strip().lower()
            if not token_clean or len(token_clean) < 3:
                continue
            if not token_clean.isalpha():
                continue
            if token_clean in stop_words or token_clean in tag_blocklist:
                continue
            if pos.startswith('NN') or pos.startswith('JJ'):
                tags.append(token_clean)

        for node in ner_tree:
            if not isinstance(node, Tree):
                continue

            label = node.label()
            entity = ' '.join(leaf[0] for leaf in node.leaves()).strip()
            if not entity:
                continue

            if label == 'PERSON':
                entity_lower = entity.lower()
                entity_words = entity_lower.split()
                
                # Skip filtered entities
                if all(word in stop_words or word in entity_blocklist for word in entity_words):
                    continue
                if len(entity_words) == 1 and (entity_lower in stop_words or entity_lower in entity_blocklist):
                    continue
                if entity.isupper() and len(entity) > 1:
                    continue
                
                people_names.append(entity)
                tags.append(entity.lower().replace(' ', '_'))
            elif label in {'GPE', 'LOCATION', 'FACILITY'}:
                places.append(entity)
                tags.append(entity.lower().replace(' ', '_'))
    except (LookupError, ValueError, TypeError):
        return {
            'tags': row_data.get('tags', ''),
            'dream_people_names': '',
            'dream_places': '',
        }
    except Exception as _nltk_exc:  # noqa: BLE001
        logging.getLogger(__name__).debug('Dream NLTK enrichment failed: %s', _nltk_exc)

    deduped_tags: list[str] = []
    seen_tags: set[str] = set()
    
    # Include original tags from Excel sheet first
    if row_data.get('tags'):
        for tag in row_data['tags'].split(','):
            tag_clean = tag.strip().lower()
            if tag_clean and tag_clean not in seen_tags and tag_clean not in tag_blocklist:
                # Filter out "image generated with prompt" pattern
                if 'image' not in tag_clean and 'generated' not in tag_clean and 'prompt' not in tag_clean:
                    seen_tags.add(tag_clean)
                    deduped_tags.append(tag_clean)
    
    # Add derived tags
    for tag in tags:
        if tag in seen_tags or tag in tag_blocklist:
            continue
        seen_tags.add(tag)
        deduped_tags.append(tag)

    def _dedupe_case_insensitive(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(value)
        return ordered

    return {
        'tags': ','.join(deduped_tags[:20]),
        'dream_people_names': ','.join(_dedupe_case_insensitive(people_names)[:20]),
        'dream_places': ','.join(_dedupe_case_insensitive(places)[:20]),
    }


# ---------------------------------------------------------------------------
# Excel parsing
# ---------------------------------------------------------------------------

def parse_excel(file_bytes: bytes) -> dict:
    """
    Parse the uploaded Excel workbook.

        Expected sheets (case-insensitive):
            - 'Daily'  — strict columns: date, title, user_entry, ai_response
      - 'Dreams' — columns: date, title, plot, cast, location, period,
                             emotion, symbols_and_imagery, insight, action, other, tags

    Returns:
                {
                    'daily':    [{'entry_date', 'title', 'user_message', 'ai_response'}, ...],
                    'dreams':   [{'entry_date', 'title', 'plot', ...}, ...],
                    'errors':   [str, ...],   # strict schema violations
                    'warnings': [str, ...],   # non-fatal parsing issues
                }
    """
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
                daily_rows.append({
                    'entry_date': entry_date,
                    'title': _sanitise(row.get('title', '')),
                    'user_message': _sanitise(row.get('user_entry', row.get('user_message', ''))),
                    'ai_response': _sanitise(row.get('ai_response', '')),
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
            _validate_sheet_headers('Dreams', df.columns.tolist(), DREAM_IMPORT_HEADERS)
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
            
            # Build row data with sanitised values
            row_data = {
                'entry_date': entry_date,
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
            }
            
            # Derive NLTK enrichment for dreams
            enriched = _derive_dream_nltk_fields(row_data)
            row_data.update(enriched)
            
            dream_rows.append(row_data)
    else:
        warnings.append("No 'Dreams' sheet found; dream entries not imported.")

    return {'daily': daily_rows, 'dreams': dream_rows, 'errors': errors, 'warnings': warnings}


# ---------------------------------------------------------------------------
# Database insertion with duplicate detection
# ---------------------------------------------------------------------------

def insert_entries(conn: sqlite3.Connection, user_id: int, parsed: dict) -> dict:
    """
    Insert parsed entries, skipping duplicates (same user_id + entry_date).

    Returns:
        {
          'inserted_daily':   int,
          'skipped_daily':    int,
          'inserted_dreams':  int,
          'skipped_dreams':   int,
          'duplicate_dates_daily':  [str, ...],
          'duplicate_dates_dreams': [str, ...],
        }
    """
    cursor = conn.cursor()

    # Fetch existing entry dates for this user upfront to minimise round-trips
    existing_daily = {
        row[0]
        for row in cursor.execute(
            'SELECT DISTINCT entry_date FROM dailydiary_entries WHERE user_id = ?',
            (user_id,),
        )
    }
    existing_dreams = {
        row[0]
        for row in cursor.execute(
            'SELECT DISTINCT entry_date FROM dreamdiary_entries WHERE user_id = ?',
            (user_id,),
        )
    }

    inserted_daily = 0
    skipped_daily = 0
    dup_daily: list[str] = []

    for row in parsed.get('daily', []):
        entry_date = row['entry_date']
        if entry_date in existing_daily:
            skipped_daily += 1
            dup_daily.append(entry_date)
            continue

        derived_fields = _derive_daily_nltk_fields(row['title'], row['user_message'])
        ai_response = _sanitise(row.get('ai_response', ''))

        # Determine next entry_number for this date
        max_num = cursor.execute(
            'SELECT MAX(entry_number) FROM dailydiary_entries '
            'WHERE user_id = ? AND entry_date = ?',
            (user_id, entry_date),
        ).fetchone()[0] or 0

        cursor.execute(
            '''INSERT INTO dailydiary_entries
               (user_id, entry_date, entry_number, title, user_message,
                ai_response, daily_people_names, daily_places, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                entry_date,
                max_num + 1,
                row['title'],
                row['user_message'],
                ai_response,
                derived_fields['daily_people_names'],
                derived_fields['daily_places'],
                derived_fields['tags'],
            ),
        )
        existing_daily.add(entry_date)
        inserted_daily += 1

    inserted_dreams = 0
    skipped_dreams = 0
    dup_dreams: list[str] = []

    for row in parsed.get('dreams', []):
        entry_date = row['entry_date']
        if entry_date in existing_dreams:
            skipped_dreams += 1
            dup_dreams.append(entry_date)
            continue

        max_num = cursor.execute(
            'SELECT MAX(entry_number) FROM dreamdiary_entries '
            'WHERE user_id = ? AND entry_date = ?',
            (user_id, entry_date),
        ).fetchone()[0] or 0

        cursor.execute(
            '''INSERT INTO dreamdiary_entries
               (user_id, entry_date, entry_number, title, "cast", location,
                period, emotion, plot, symbols_and_imagery, insight, action, other,
                tags, dream_people_names, dream_places)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                entry_date,
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
        existing_dreams.add(entry_date)
        inserted_dreams += 1

    conn.commit()

    return {
        'inserted_daily': inserted_daily,
        'skipped_daily': skipped_daily,
        'inserted_dreams': inserted_dreams,
        'skipped_dreams': skipped_dreams,
        'duplicate_dates_daily': dup_daily,
        'duplicate_dates_dreams': dup_dreams,
    }


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


def ensure_history_table(conn: sqlite3.Connection) -> None:
    """Create or repair import_history table for older local databases."""
    conn.execute(IMPORT_HISTORY_DDL)

    table_info_rows = conn.execute('PRAGMA table_info(import_history)').fetchall()
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

    columns = {
        row[1]: row for row in conn.execute('PRAGMA table_info(import_history)').fetchall()
    }

    if 'imported_at' not in columns:
        conn.execute("ALTER TABLE import_history ADD COLUMN imported_at TEXT")
        if 'import_date' in columns:
            conn.execute(
                "UPDATE import_history SET imported_at = COALESCE(import_date, datetime('now'))"
            )
        else:
            conn.execute(
                "UPDATE import_history SET imported_at = datetime('now')"
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
        '''INSERT INTO import_history
           (user_id, imported_at, filename, file_size_bytes,
            inserted_daily, skipped_daily, inserted_dreams, skipped_dreams,
            warnings, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
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
    conn.commit()
    return cursor.lastrowid


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

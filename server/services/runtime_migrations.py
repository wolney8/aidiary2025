"""Runtime database schema migrations for compatibility across deployed DBs."""

from __future__ import annotations

import sqlite3
from typing import Callable


_TARGET_COLUMNS: dict[str, dict[str, str]] = {
    'dailydiary_entries': {
        'import_id': 'INTEGER',
        'entry_time': 'TEXT',
        'mood': 'TEXT',
        'ai_style': 'TEXT',
        'ai_response': 'TEXT',
        'image_prompt': 'TEXT',
        'image_url': 'TEXT',
        'image_storage_key': 'TEXT',
        'image_source': 'TEXT',
        'recycled_image_prompt': 'TEXT',
        'image_position_x': 'REAL DEFAULT 50',
        'image_position_y': 'REAL DEFAULT 50',
        'analysis_attachment_refs': 'TEXT',
    },
    'dreamdiary_entries': {
        'import_id': 'INTEGER',
        'entry_time': 'TEXT',
        'mood': 'TEXT',
        'ai_style': 'TEXT',
        'summary': 'TEXT',
        'interpretation': 'TEXT',
        'image_prompt': 'TEXT',
        'image_url': 'TEXT',
        'image_storage_key': 'TEXT',
        'image_source': 'TEXT',
        'recycled_image_prompt': 'TEXT',
        'image_position_x': 'REAL DEFAULT 50',
        'image_position_y': 'REAL DEFAULT 50',
        'analysis_attachment_refs': 'TEXT',
    },
}

_USER_SETTINGS_COLUMNS: dict[str, str] = {
    'profile_picture_storage_key': 'TEXT',
    'display_name': 'TEXT',
    'pronouns': 'TEXT',
    'gender': 'TEXT',
    'custom_guidance': 'TEXT',
    'timezone': "TEXT DEFAULT 'UTC'",
    'holiday_country_code': 'TEXT',
    'show_public_holidays': 'INTEGER DEFAULT 0',
    'show_on_this_day': 'INTEGER DEFAULT 0',
    'ai_tone': "TEXT DEFAULT 'friendly'",
    'ai_verbosity': "TEXT DEFAULT 'balanced'",
    'ai_focus': "TEXT DEFAULT 'reflective'",
    'ai_model': "TEXT DEFAULT 'gpt-4.1-mini'",
    'allow_ai_history': 'INTEGER DEFAULT 1',
    'allow_ai_attachment_context': 'INTEGER DEFAULT 0',
    'writing_reminders_enabled': 'INTEGER DEFAULT 0',
    'writing_reminder_days': 'TEXT',
    'writing_reminder_time': "TEXT DEFAULT '19:00'",
    'writing_reminder_silence_days': 'INTEGER DEFAULT 3',
    'writing_reminder_entry_types': "TEXT DEFAULT 'daily,dream'",
    'writing_rhythm_progress_enabled': 'INTEGER DEFAULT 0',
    'writing_rhythm_weekly_goal': 'INTEGER DEFAULT 4',
}

_EXPORT_HISTORY_DDL = """
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
"""

_IMPORT_SESSIONS_DDL = """
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
"""

_IMPORT_JOBS_DDL = """
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
"""

_ENTRY_ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS entry_assets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    entry_type        TEXT NOT NULL,
    entry_id          INTEGER NOT NULL,
    asset_role        TEXT NOT NULL DEFAULT 'attachment',
    storage_key       TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type         TEXT NOT NULL,
    file_size_bytes   INTEGER NOT NULL DEFAULT 0,
    sort_order        INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_ENTRY_ASSET_COLUMNS: dict[str, str] = {
    'derived_text': 'TEXT',
    'derived_text_source': 'TEXT',
    'derived_text_updated_at': 'TEXT',
}

_IMPORTANT_DAYS_DDL = """
CREATE TABLE IF NOT EXISTS important_days (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    label         TEXT NOT NULL,
    starts_on     TEXT,
    month         INTEGER NOT NULL,
    day           INTEGER NOT NULL,
    original_year INTEGER,
    category      TEXT NOT NULL DEFAULT 'other',
    recurrence    TEXT NOT NULL DEFAULT 'yearly',
    icon_name     TEXT NOT NULL DEFAULT 'event',
    accent_color  TEXT NOT NULL DEFAULT 'amber',
    image_url     TEXT,
    image_storage_key TEXT,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

_IMPORTANT_DAY_COLUMNS: dict[str, str] = {
    'starts_on': 'TEXT',
    'recurrence': "TEXT NOT NULL DEFAULT 'yearly'",
    'icon_name': "TEXT NOT NULL DEFAULT 'event'",
    'accent_color': "TEXT NOT NULL DEFAULT 'amber'",
    'image_url': 'TEXT',
    'image_storage_key': 'TEXT',
}

_PUBLIC_HOLIDAY_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS public_holiday_cache (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code  TEXT NOT NULL,
    holiday_year  INTEGER NOT NULL,
    payload_json  TEXT NOT NULL,
    fetched_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, holiday_year)
)
"""

_ENTRY_RESURFACING_PREFERENCES_DDL = """
CREATE TABLE IF NOT EXISTS entry_resurfacing_preferences (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    entry_type TEXT NOT NULL
               CHECK(entry_type IN ('daily', 'dream', 'thought_record')),
    entry_id   INTEGER NOT NULL,
    hidden_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, entry_type, entry_id)
)
"""

_REFLECTION_SUMMARIES_DDL = """
CREATE TABLE IF NOT EXISTS reflection_summaries (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    period_type        TEXT NOT NULL CHECK(period_type IN ('weekly', 'monthly')),
    period_start       TEXT NOT NULL,
    period_end         TEXT NOT NULL,
    title              TEXT NOT NULL,
    summary_text       TEXT NOT NULL,
    themes_json        TEXT NOT NULL DEFAULT '[]',
    source_refs_json   TEXT NOT NULL DEFAULT '[]',
    model              TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, period_type, period_start)
)
"""

_CHAT_MESSAGES_DDL = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    conversation_id TEXT NOT NULL,
    request_id      TEXT,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    token_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

_CBT_WORKSHEETS_DDL = """
CREATE TABLE IF NOT EXISTS cbt_worksheets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    worksheet_type    TEXT NOT NULL DEFAULT 'thought_record',
    title             TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft', 'completed')),
    current_step      INTEGER NOT NULL DEFAULT 1 CHECK(current_step BETWEEN 1 AND 7),
    record_date       TEXT NOT NULL DEFAULT CURRENT_DATE,
    linked_entry_type TEXT CHECK(linked_entry_type IN ('daily', 'dream')),
    linked_entry_id   INTEGER,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at      TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(
        (linked_entry_type IS NULL AND linked_entry_id IS NULL) OR
        (linked_entry_type IS NOT NULL AND linked_entry_id IS NOT NULL)
    )
)
"""

_CBT_THOUGHT_RECORD_DATA_DDL = """
CREATE TABLE IF NOT EXISTS cbt_thought_record_data (
    worksheet_id         INTEGER PRIMARY KEY,
    situation            TEXT NOT NULL DEFAULT '',
    feelings_before_json TEXT NOT NULL DEFAULT '[]',
    unhelpful_thoughts   TEXT NOT NULL DEFAULT '',
    evidence_for         TEXT NOT NULL DEFAULT '',
    evidence_against     TEXT NOT NULL DEFAULT '',
    balanced_thought     TEXT NOT NULL DEFAULT '',
    feelings_after_json  TEXT NOT NULL DEFAULT '[]',
    next_step            TEXT NOT NULL DEFAULT '',
    ai_response          TEXT NOT NULL DEFAULT '',
    ai_responded_at      TEXT,
    ai_response_outdated INTEGER NOT NULL DEFAULT 0
                         CHECK(ai_response_outdated IN (0, 1)),
    FOREIGN KEY (worksheet_id) REFERENCES cbt_worksheets(id) ON DELETE CASCADE
)
"""

_CBT_THOUGHT_RECORD_DATA_COLUMNS: dict[str, str] = {
    'ai_response': "TEXT NOT NULL DEFAULT ''",
    'ai_responded_at': 'TEXT',
    'ai_response_outdated': 'INTEGER NOT NULL DEFAULT 0 CHECK(ai_response_outdated IN (0, 1))',
}


def ensure_entry_mood_style_columns(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> int:
    """Ensure runtime diary tables include compatibility columns.

    Returns the number of columns added across all target tables.
    Safe to run repeatedly (idempotent).
    """
    added_columns = 0

    with sqlite3.connect(database_path, timeout=10) as conn:
        cursor = conn.cursor()

        for table_name, required_columns in _TARGET_COLUMNS.items():
            table_exists = cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if not table_exists:
                if log:
                    log('Runtime migration skipped missing table: %s', table_name)
                continue

            table_columns = {
                row[1]
                for row in cursor.execute(f'PRAGMA table_info({table_name})').fetchall()
            }

            for column_name, column_definition in required_columns.items():
                if column_name in table_columns:
                    continue
                cursor.execute(
                    f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}'
                )
                added_columns += 1
                if log:
                    log('Runtime migration added column %s.%s', table_name, column_name)

    return added_columns


def ensure_entry_ai_metadata_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime metadata table exists for AI context headers.

    Returns True when creation check is executed successfully.
    Safe to run repeatedly (idempotent).
    """
    with sqlite3.connect(database_path, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entry_ai_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                reference_date DATE,
                summary_header TEXT,
                tags TEXT,
                people_names TEXT,
                places TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'entry_ai_metadata')

    return True


def ensure_user_settings_columns(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> int:
    """Ensure runtime users table includes settings and personalisation columns."""
    added_columns = 0

    with sqlite3.connect(database_path, timeout=10) as conn:
        cursor = conn.cursor()

        table_exists = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('users',),
        ).fetchone()
        if not table_exists:
            if log:
                log('Runtime migration skipped missing table: %s', 'users')
            return 0

        table_columns = {
            row[1]
            for row in cursor.execute('PRAGMA table_info(users)').fetchall()
        }

        for column_name, column_definition in _USER_SETTINGS_COLUMNS.items():
            if column_name in table_columns:
                continue
            cursor.execute(
                f'ALTER TABLE users ADD COLUMN {column_name} {column_definition}'
            )
            added_columns += 1
            if log:
                log('Runtime migration added column %s.%s', 'users', column_name)

    return added_columns


def ensure_export_history_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime export-history table exists for guarded bulk delete."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_EXPORT_HISTORY_DDL)

    if log:
        log('Runtime migration ensured table exists: %s', 'export_history')

    return True


def ensure_import_sessions_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime staged import-sessions table exists for duplicate review."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_IMPORT_SESSIONS_DDL)

    if log:
        log('Runtime migration ensured table exists: %s', 'import_sessions')

    return True


def ensure_import_jobs_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure durable background import jobs survive process restarts."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_IMPORT_JOBS_DDL)
        columns = {
            row[1] for row in conn.execute('PRAGMA table_info(import_jobs)').fetchall()
        }
        if 'worker_token' not in columns:
            conn.execute('ALTER TABLE import_jobs ADD COLUMN worker_token TEXT')
        if 'lease_expires_at' not in columns:
            conn.execute('ALTER TABLE import_jobs ADD COLUMN lease_expires_at TEXT')
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_import_jobs_user_status
            ON import_jobs(user_id, status, updated_at)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'import_jobs')
    return True


def ensure_entry_assets_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime entry-assets table exists for non-hero attachments."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_ENTRY_ASSETS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entry_assets_lookup
            ON entry_assets(user_id, entry_type, entry_id, sort_order, id)
            """
        )
        table_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(entry_assets)').fetchall()
        }
        for column_name, column_definition in _ENTRY_ASSET_COLUMNS.items():
            if column_name in table_columns:
                continue
            conn.execute(
                f'ALTER TABLE entry_assets ADD COLUMN {column_name} {column_definition}'
            )
            if log:
                log('Runtime migration added column %s.%s', 'entry_assets', column_name)

    if log:
        log('Runtime migration ensured table exists: %s', 'entry_assets')

    return True


def ensure_important_days_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime important-days table exists for user-managed recurring dates."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_IMPORTANT_DAYS_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_important_days_user_lookup
            ON important_days(user_id, month, day)
            """
        )
        table_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(important_days)').fetchall()
        }
        for column_name, column_definition in _IMPORTANT_DAY_COLUMNS.items():
            if column_name in table_columns:
                continue
            conn.execute(
                f'ALTER TABLE important_days ADD COLUMN {column_name} {column_definition}'
            )
            if log:
                log('Runtime migration added column %s.%s', 'important_days', column_name)

    if log:
        log('Runtime migration ensured table exists: %s', 'important_days')

    return True


def ensure_public_holiday_cache_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure runtime public-holiday cache table exists for provider responses."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_PUBLIC_HOLIDAY_CACHE_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_public_holiday_cache_lookup
            ON public_holiday_cache(country_code, holiday_year)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'public_holiday_cache')

    return True


def ensure_entry_resurfacing_preferences_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure per-user hidden-memory preferences are stored durably."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_ENTRY_RESURFACING_PREFERENCES_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_entry_resurfacing_user_lookup
            ON entry_resurfacing_preferences(user_id, entry_type, entry_id)
            """
        )

    if log:
        log(
            'Runtime migration ensured table exists: %s',
            'entry_resurfacing_preferences',
        )
    return True


def ensure_reflection_summaries_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure generated weekly/monthly reflection summaries are persisted."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_REFLECTION_SUMMARIES_DDL)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reflection_summaries_user_period
            ON reflection_summaries(user_id, period_type, period_start DESC)
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'reflection_summaries')

    return True


def ensure_chat_messages_table(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure durable, user-scoped storage exists for chat conversations."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute(_CHAT_MESSAGES_DDL)
        columns = {
            row[1] for row in conn.execute('PRAGMA table_info(chat_messages)').fetchall()
        }
        if 'request_id' not in columns:
            conn.execute('ALTER TABLE chat_messages ADD COLUMN request_id TEXT')
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation
            ON chat_messages(user_id, conversation_id, created_at, id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created
            ON chat_messages(user_id, created_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_messages_request_role
            ON chat_messages(user_id, request_id, role)
            WHERE request_id IS NOT NULL
            """
        )

    if log:
        log('Runtime migration ensured table exists: %s', 'chat_messages')

    return True


def ensure_cbt_worksheet_tables(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> bool:
    """Ensure additive, user-scoped storage exists for structured CBT worksheets."""
    with sqlite3.connect(database_path, timeout=10) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute(_CBT_WORKSHEETS_DDL)
        conn.execute(_CBT_THOUGHT_RECORD_DATA_DDL)
        worksheet_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(cbt_worksheets)').fetchall()
        }
        if 'record_date' not in worksheet_columns:
            conn.execute('ALTER TABLE cbt_worksheets ADD COLUMN record_date TEXT')
            if log:
                log('Runtime migration added column %s.%s', 'cbt_worksheets', 'record_date')
        data_columns = {
            row[1]
            for row in conn.execute('PRAGMA table_info(cbt_thought_record_data)').fetchall()
        }
        for column_name, column_definition in _CBT_THOUGHT_RECORD_DATA_COLUMNS.items():
            if column_name in data_columns:
                continue
            conn.execute(
                f'ALTER TABLE cbt_thought_record_data ADD COLUMN {column_name} {column_definition}'
            )
            if log:
                log(
                    'Runtime migration added column %s.%s',
                    'cbt_thought_record_data',
                    column_name,
                )
        conn.execute(
            """
            UPDATE cbt_worksheets
            SET record_date = COALESCE(
                CASE linked_entry_type
                    WHEN 'daily' THEN (
                        SELECT entry_date
                        FROM dailydiary_entries
                        WHERE id = linked_entry_id AND user_id = cbt_worksheets.user_id
                    )
                    WHEN 'dream' THEN (
                        SELECT entry_date
                        FROM dreamdiary_entries
                        WHERE id = linked_entry_id AND user_id = cbt_worksheets.user_id
                    )
                END,
                date(created_at),
                date('now')
            )
            WHERE record_date IS NULL OR record_date = ''
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_user_status
            ON cbt_worksheets(user_id, status, updated_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_linked_entry
            ON cbt_worksheets(user_id, linked_entry_type, linked_entry_id)
            WHERE linked_entry_id IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_user_date
            ON cbt_worksheets(user_id, record_date, id)
            """
        )

    if log:
        log('Runtime migration ensured CBT worksheet tables exist')
    return True

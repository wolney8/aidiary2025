"""Runtime database schema migrations for compatibility across deployed DBs."""

from __future__ import annotations

import sqlite3
from typing import Callable


_TARGET_COLUMNS: dict[str, tuple[str, ...]] = {
    'dailydiary_entries': ('mood', 'ai_style', 'ai_response'),
    'dreamdiary_entries': (
        'mood',
        'ai_style',
        'summary',
        'interpretation',
        'image_prompt',
        'image_url',
        'recycled_image_prompt',
    ),
}

_USER_SETTINGS_COLUMNS: dict[str, str] = {
    'display_name': 'TEXT',
    'pronouns': 'TEXT',
    'timezone': "TEXT DEFAULT 'UTC'",
    'ai_tone': "TEXT DEFAULT 'friendly'",
    'ai_verbosity': "TEXT DEFAULT 'balanced'",
    'ai_focus': "TEXT DEFAULT 'reflective'",
    'allow_ai_history': 'INTEGER DEFAULT 1',
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

            for column_name in required_columns:
                if column_name in table_columns:
                    continue
                cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT')
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

"""Runtime database schema migrations for compatibility across deployed DBs."""

from __future__ import annotations

import sqlite3
from typing import Callable


_TARGET_COLUMNS: dict[str, tuple[str, ...]] = {
    'dailydiary_entries': ('mood', 'ai_style'),
    'dreamdiary_entries': ('mood', 'ai_style'),
}


def ensure_entry_mood_style_columns(
    database_path: str,
    log: Callable[[str, object], None] | None = None,
) -> int:
    """Ensure runtime diary tables include mood/ai_style columns.

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
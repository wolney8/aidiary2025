"""User account deletion helpers.

Keep account deletion centralised so production hardening can review one
database/media cleanup path instead of scattered route-specific deletes.
"""

from __future__ import annotations

from collections.abc import Iterable

from services.media_storage import delete_image


_USER_TABLES: tuple[str, ...] = (
    "chat_messages",
    "chat_observability_events",
    "entry_ai_metadata",
    "entry_resurfacing_preferences",
    "reflection_summaries",
    "cbt_thought_record_data",
    "cbt_worksheets",
    "important_days",
    "entry_assets",
    "import_jobs",
    "import_sessions",
    "export_history",
    "import_history",
    "auth_identities",
    "configurations",
    "dailydiary_entries",
    "dreamdiary_entries",
)


def collect_user_media_storage_keys(conn, user_id: int) -> set[str]:
    """Return storage keys that should be removed with the account."""
    storage_keys: set[str] = set()

    for table_name in ("dailydiary_entries", "dreamdiary_entries", "important_days"):
        storage_keys.update(
            _fetch_storage_keys(
                conn,
                f"SELECT image_storage_key FROM {table_name} WHERE user_id = ?",
                (user_id,),
                column_name="image_storage_key",
            )
        )

    storage_keys.update(
        _fetch_storage_keys(
            conn,
            "SELECT storage_key FROM entry_assets WHERE user_id = ?",
            (user_id,),
            column_name="storage_key",
        )
    )
    storage_keys.update(
        _fetch_storage_keys(
            conn,
            "SELECT profile_picture_storage_key FROM users WHERE id = ?",
            (user_id,),
            column_name="profile_picture_storage_key",
        )
    )

    return storage_keys


def delete_user_account_data(conn, user_id: int) -> None:
    """Delete all app-owned database rows for a user.

    This is intentionally explicit instead of relying on foreign-key cascades
    because local SQLite test/runtime databases do not always enforce them.
    """
    for table_name in _USER_TABLES:
        try:
            if table_name == "cbt_thought_record_data":
                conn.execute(
                    """
                    DELETE FROM cbt_thought_record_data
                    WHERE worksheet_id IN (
                        SELECT id FROM cbt_worksheets WHERE user_id = ?
                    )
                    """,
                    (user_id,),
                )
                continue

            conn.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (user_id,))
        except Exception as exc:
            if not _is_missing_table_error(exc):
                raise

    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def delete_user_media(storage_keys: Iterable[str]) -> None:
    for storage_key in storage_keys:
        delete_image(storage_key)


def _fetch_storage_keys(
    conn,
    sql: str,
    params: tuple[object, ...],
    *,
    column_name: str,
) -> set[str]:
    keys: set[str] = set()
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return keys

    for row in rows:
        value = row[column_name]
        if value:
            keys.add(str(value))
    return keys


def _is_missing_table_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "no such table" in message
        or "does not exist" in message
        or "undefinedtable" in exc.__class__.__name__.lower()
    )

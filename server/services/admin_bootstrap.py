"""Helpers for explicit administrator bootstrap configuration."""

from __future__ import annotations

import os
from typing import Any

from services.billing_entitlements import upsert_user_entitlement


def configured_admin_identifiers() -> set[str]:
    raw_users = ",".join(
        value
        for value in (
            os.getenv("OPENMYND_BOOTSTRAP_ADMIN_USERS"),
            os.getenv("OPENMYND_ADMIN_USERS"),
            os.getenv("OPENMYND_ADMIN_EMAILS"),
            os.getenv("BOOTSTRAP_ADMIN_USERS"),
            os.getenv("ADMIN_USERS"),
        )
        if value
    ).strip()
    return {
        item.strip().lower()
        for item in raw_users.split(",")
        if item.strip()
    }


def ensure_bootstrap_admin_for_user(conn: Any, user: Any, logger: Any | None = None) -> bool:
    """Grant administrator entitlement when the current user matches env config."""
    identifiers = configured_admin_identifiers()
    if not identifiers or user is None:
        return False

    user_id = int(_row_get(user, "id") or 0)
    username = str(_row_get(user, "username") or "").strip().lower()
    email = str(_row_get(user, "email") or "").strip().lower()
    if not user_id or (username not in identifiers and email not in identifiers):
        return False

    upsert_user_entitlement(
        conn,
        user_id=user_id,
        tier="administrator",
        source="manual",
        status="active",
    )
    if logger:
        logger.info("Bootstrap admin entitlement ensured for user_id=%s", user_id)
    return True


def ensure_configured_admins(conn: Any, logger: Any | None = None) -> int:
    """Grant administrator entitlement to all configured existing users."""
    count = 0
    for identifier in sorted(configured_admin_identifiers()):
        row = conn.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE LOWER(COALESCE(username, '')) = ?
               OR LOWER(COALESCE(email, '')) = ?
            LIMIT 1
            """,
            (identifier, identifier),
        ).fetchone()
        if not row:
            if logger:
                logger.info("Bootstrap admin target not found yet: %s", identifier)
            continue
        if ensure_bootstrap_admin_for_user(conn, row, logger):
            count += 1
    return count


def _row_get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, None)

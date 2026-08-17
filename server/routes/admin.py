"""Administrator console and platform announcement routes."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.billing_entitlements import (
    VALID_STATUSES,
    VALID_TIERS,
    resolve_user_entitlement,
    upsert_user_entitlement,
)
from services.account_deletion import (
    collect_user_media_storage_keys,
    delete_user_account_data,
    delete_user_media,
)
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.email_delivery import EmailDeliveryError, send_transactional_email
from services.plan_catalogue import list_plan_catalogue, seed_default_plan_catalogue, upsert_plan
from services.security_audit_report import build_security_audit_report
from services.sql_compat import append_returning_id, inserted_id
from services.stripe_billing import (
    configured_checkout_periods,
    configured_checkout_tiers,
    load_stripe_billing_config,
)
from services.media_storage import health_check as media_storage_health_check
from scripts.validate_database_maintenance import (
    DEFAULT_MAX_AGE_HOURS as DEFAULT_DATABASE_MAINTENANCE_MAX_AGE_HOURS,
    build_database_maintenance_report,
)
from scripts.create_sqlite_backup import DEFAULT_BACKUP_DIR
from scripts.export_postgres_snapshot import DEFAULT_SNAPSHOT_DIR
from scripts.run_database_backup_bundle import DEFAULT_MEDIA_BACKUP_DIR
from scripts.validate_production_preflight import build_production_preflight
from services.usage_limits import get_user_usage_summary


admin_bp = Blueprint("admin", __name__)

ANNOUNCEMENT_SEVERITIES = {"info", "success", "warning", "critical"}
ANNOUNCEMENT_PLACEMENTS = {"banner", "bell", "both"}
ANNOUNCEMENT_STATUSES = {"draft", "published", "archived"}
ANNOUNCEMENT_TARGET_TYPES = {"all", "tier", "user"}
ANNOUNCEMENT_TIMEZONES = {
    "Europe/London",
    "UTC",
    "Europe/Dublin",
    "Europe/Paris",
    "America/New_York",
    "America/Los_Angeles",
    "Australia/Sydney",
}
ACCOUNT_STATUSES = {"active", "restricted"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLACEHOLDER_CONFIG_MARKERS = ("your_", "your-", "replace-", "example", "changeme")


def _database_adapter() -> DatabaseAdapter:
    return current_app.config["DATABASE_ADAPTER"]


def _database_provider() -> str:
    return current_app.config.get("DATABASE_PROVIDER", SQLITE_PROVIDER)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _configured_non_placeholder(value: str | None) -> bool:
    normalised = (value or "").strip().lower()
    return bool(normalised) and not any(
        marker in normalised for marker in PLACEHOLDER_CONFIG_MARKERS
    )


def get_db():
    return _database_adapter().connect(timeout=10)


def _row_get(row, key: str):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, None)


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _require_admin(conn, user_id: int) -> tuple[bool, dict[str, object]]:
    entitlement = resolve_user_entitlement(conn, user_id)
    return entitlement.get("tier") == "administrator", entitlement


def _forbid_non_admin(conn, user_id: int):
    is_admin, entitlement = _require_admin(conn, user_id)
    if not is_admin:
        return jsonify({"error": "Administrator access is required."}), 403
    return None


def _table_columns(conn, table_name: str) -> set[str]:
    return _database_adapter().table_columns(conn, table_name)


def _ensure_account_status_column(conn) -> None:
    if "account_status" in _table_columns(conn, "users"):
        return
    conn.execute("ALTER TABLE users ADD COLUMN account_status TEXT DEFAULT 'active'")


def _clean_text(value: object, *, max_length: int, fallback: str = "") -> str:
    text = str(value or "").strip()
    text = " ".join(text.split())
    if not text:
        text = fallback
    return text[:max_length]


def _serialise_target(row) -> dict[str, str | None]:
    return {
        "type": str(_row_get(row, "target_type") or "all"),
        "value": _row_get(row, "target_value"),
    }


def _announcement_targets(conn, announcement_id: int) -> list[dict[str, str | None]]:
    rows = conn.execute(
        """
        SELECT target_type, target_value
        FROM admin_announcement_targets
        WHERE announcement_id = ?
        ORDER BY id ASC
        """,
        (announcement_id,),
    ).fetchall()
    return [_serialise_target(row) for row in rows] or [{"type": "all", "value": None}]


def _serialise_announcement(row, targets: list[dict[str, str | None]] | None = None) -> dict[str, object]:
    announcement_id = int(_row_get(row, "id"))
    return {
        "id": announcement_id,
        "title": _row_get(row, "title") or "",
        "message": _row_get(row, "message") or "",
        "severity": _row_get(row, "severity") or "info",
        "placement": _row_get(row, "placement") or "banner",
        "status": _row_get(row, "status") or "draft",
        "starts_at": _row_get(row, "starts_at"),
        "ends_at": _row_get(row, "ends_at"),
        "timezone": _row_get(row, "timezone") or "Europe/London",
        "dismissible": bool(_row_get(row, "dismissible")),
        "created_by": _row_get(row, "created_by"),
        "created_at": _row_get(row, "created_at"),
        "updated_at": _row_get(row, "updated_at"),
        "read_count": int(_row_get(row, "read_count") or 0),
        "dismissed_count": int(_row_get(row, "dismissed_count") or 0),
        "targets": targets or [],
    }


def _normalise_targets(raw_targets: object) -> list[dict[str, str | None]]:
    targets: list[dict[str, str | None]] = []
    if isinstance(raw_targets, list):
        for item in raw_targets:
            if not isinstance(item, dict):
                continue
            target_type = str(item.get("type") or item.get("target_type") or "").strip().lower()
            target_value = str(item.get("value") or item.get("target_value") or "").strip()
            if target_type not in ANNOUNCEMENT_TARGET_TYPES:
                continue
            if target_type == "all":
                targets.append({"type": "all", "value": None})
                continue
            if target_value:
                targets.append({"type": target_type, "value": target_value[:120]})
    if not targets:
        return [{"type": "all", "value": None}]
    if any(target["type"] == "all" for target in targets):
        return [{"type": "all", "value": None}]
    deduped: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for target in targets:
        key = (str(target["type"]), target["value"])
        if key not in seen:
            deduped.append(target)
            seen.add(key)
    return deduped[:40]


def _announcement_payload(payload: dict[str, object]) -> dict[str, object]:
    title = _clean_text(payload.get("title"), max_length=90)
    message = _clean_text(payload.get("message"), max_length=500)
    if not title:
        raise ValueError("Announcement title is required.")
    if not message:
        raise ValueError("Announcement message is required.")
    severity = str(payload.get("severity") or "info").strip().lower()
    placement = str(payload.get("placement") or "banner").strip().lower()
    status = str(payload.get("status") or "draft").strip().lower()
    if severity not in ANNOUNCEMENT_SEVERITIES:
        raise ValueError("Choose a valid announcement severity.")
    if placement not in ANNOUNCEMENT_PLACEMENTS:
        raise ValueError("Choose a valid announcement placement.")
    if status not in ANNOUNCEMENT_STATUSES:
        raise ValueError("Choose a valid announcement status.")
    announcement_timezone = _normalise_timezone(payload.get("timezone"))
    starts_at = str(payload.get("starts_at") or "").strip()[:40] or None
    ends_at = str(payload.get("ends_at") or "").strip()[:40] or None
    if starts_at:
        starts_dt = _parse_announcement_datetime(starts_at, announcement_timezone)
        if starts_dt < datetime.now(timezone.utc) - timedelta(minutes=2):
            raise ValueError("Announcement start time cannot be in the past.")
    else:
        starts_dt = None
    if ends_at:
        ends_dt = _parse_announcement_datetime(ends_at, announcement_timezone)
        if ends_dt < datetime.now(timezone.utc) - timedelta(minutes=2):
            raise ValueError("Announcement end time cannot be in the past.")
        if starts_dt and ends_dt <= starts_dt:
            raise ValueError("Announcement end time must be after the start time.")
    return {
        "title": title,
        "message": message,
        "severity": severity,
        "placement": placement,
        "status": status,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "timezone": announcement_timezone,
        "dismissible": 1 if bool(payload.get("dismissible", True)) else 0,
        "targets": _normalise_targets(payload.get("targets")),
    }


def _normalise_timezone(value: object) -> str:
    text = str(value or "Europe/London").strip()
    if text not in ANNOUNCEMENT_TIMEZONES:
        raise ValueError("Choose a supported announcement timezone.")
    return text


def _parse_announcement_datetime(value: object, announcement_timezone: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    normalised = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError as exc:
        raise ValueError("Use a valid announcement date and time.") from exc
    if parsed.tzinfo is None:
        try:
            parsed = parsed.replace(tzinfo=ZoneInfo(announcement_timezone))
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Choose a supported announcement timezone.") from exc
    return parsed.astimezone(timezone.utc)


def _announcement_is_active(row) -> bool:
    if str(_row_get(row, "status") or "") != "published":
        return False
    announcement_timezone = str(_row_get(row, "timezone") or "Europe/London")
    now = datetime.now(timezone.utc)
    starts_at = _row_get(row, "starts_at")
    ends_at = _row_get(row, "ends_at")
    try:
        if starts_at and _parse_announcement_datetime(starts_at, announcement_timezone) > now:
            return False
        if ends_at and _parse_announcement_datetime(ends_at, announcement_timezone) < now:
            return False
    except ValueError:
        current_app.logger.warning(
            "Skipping announcement %s with invalid active window",
            _row_get(row, "id"),
        )
        return False
    return True


def _write_announcement_targets(conn, announcement_id: int, targets: list[dict[str, str | None]]) -> None:
    conn.execute(
        "DELETE FROM admin_announcement_targets WHERE announcement_id = ?",
        (announcement_id,),
    )
    conn.executemany(
        """
        INSERT INTO admin_announcement_targets (announcement_id, target_type, target_value)
        VALUES (?, ?, ?)
        """,
        [
            (announcement_id, target["type"], target.get("value"))
            for target in targets
        ],
    )


def _get_announcement(conn, announcement_id: int):
    return conn.execute(
        """
        SELECT a.id, a.title, a.message, a.severity, a.placement, a.status,
               a.starts_at, a.ends_at, a.timezone, a.dismissible, a.created_by,
               a.created_at, a.updated_at,
               COALESCE(SUM(CASE WHEN s.read_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS read_count,
               COALESCE(SUM(CASE WHEN s.dismissed_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS dismissed_count
        FROM admin_announcements
        a
        LEFT JOIN admin_announcement_user_state s ON s.announcement_id = a.id
        WHERE a.id = ?
        GROUP BY a.id, a.title, a.message, a.severity, a.placement, a.status,
                 a.starts_at, a.ends_at, a.timezone, a.dismissible, a.created_by,
                 a.created_at, a.updated_at
        """,
        (announcement_id,),
    ).fetchone()


def _list_announcements(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT a.id, a.title, a.message, a.severity, a.placement, a.status,
               a.starts_at, a.ends_at, a.timezone, a.dismissible, a.created_by,
               a.created_at, a.updated_at,
               COALESCE(SUM(CASE WHEN s.read_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS read_count,
               COALESCE(SUM(CASE WHEN s.dismissed_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS dismissed_count
        FROM admin_announcements a
        LEFT JOIN admin_announcement_user_state s ON s.announcement_id = a.id
        GROUP BY a.id, a.title, a.message, a.severity, a.placement, a.status,
                 a.starts_at, a.ends_at, a.timezone, a.dismissible, a.created_by,
                 a.created_at, a.updated_at
        ORDER BY
            CASE a.status WHEN 'published' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END,
            a.updated_at DESC,
            a.id DESC
        LIMIT 100
        """
    ).fetchall()
    return [
        _serialise_announcement(row, _announcement_targets(conn, int(_row_get(row, "id"))))
        for row in rows
    ]


def _target_matches(targets: list[dict[str, str | None]], *, user_id: int, tier: str) -> bool:
    for target in targets:
        target_type = target.get("type")
        value = str(target.get("value") or "").strip().lower()
        if target_type == "all":
            return True
        if target_type == "tier" and value == tier.lower():
            return True
        if target_type == "user" and value == str(user_id):
            return True
    return False


def _active_announcements_for_user(conn, user_id: int) -> list[dict[str, object]]:
    entitlement = resolve_user_entitlement(conn, user_id)
    tier = str(entitlement.get("tier") or "free")
    rows = conn.execute(
        """
        SELECT a.id, a.title, a.message, a.severity, a.placement, a.status,
               a.starts_at, a.ends_at, a.timezone, a.dismissible, a.created_by,
               a.created_at, a.updated_at, s.read_at, s.dismissed_at,
               0 AS read_count, 0 AS dismissed_count
        FROM admin_announcements a
        LEFT JOIN admin_announcement_user_state s
          ON s.announcement_id = a.id AND s.user_id = ?
        WHERE a.status = 'published'
        ORDER BY
          CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 WHEN 'success' THEN 2 ELSE 3 END,
          a.updated_at DESC,
          a.id DESC
        LIMIT 50
        """,
        (user_id,),
    ).fetchall()
    active: list[dict[str, object]] = []
    for row in rows:
        announcement_id = int(_row_get(row, "id"))
        if not _announcement_is_active(row):
            continue
        targets = _announcement_targets(conn, announcement_id)
        if not _target_matches(targets, user_id=user_id, tier=tier):
            continue
        dismissed = _row_get(row, "dismissed_at") is not None
        if dismissed:
            continue
        item = _serialise_announcement(row, targets)
        item["unread"] = _row_get(row, "read_at") is None
        item["dismissed"] = False
        active.append(item)
    return active


def _touch_announcement_state(conn, announcement_id: int, user_id: int, field: str) -> None:
    if field not in {"read_at", "dismissed_at"}:
        raise ValueError("Invalid announcement state field.")
    conn.execute(
        f"""
        INSERT INTO admin_announcement_user_state (
            announcement_id, user_id, {field}, updated_at
        )
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(announcement_id, user_id) DO UPDATE SET
            {field} = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (announcement_id, user_id),
    )


def _auth_methods_for_user(conn, user_id: int, password_auth_enabled: object | None) -> list[str]:
    methods: list[str] = []
    try:
        rows = conn.execute(
            """
            SELECT provider
            FROM auth_identities
            WHERE user_id = ?
            ORDER BY provider ASC
            """,
            (user_id,),
        ).fetchall()
        methods.extend(str(_row_get(row, "provider") or "").strip() for row in rows)
    except Exception:
        pass
    if int(password_auth_enabled or 0) == 1:
        methods.append("password")
    return sorted({method for method in methods if method})


def _current_subscription_for_user(conn, user_id: int) -> dict[str, object] | None:
    row = conn.execute(
        """
        SELECT provider, provider_subscription_id, tier, status, billing_period,
               current_period_end, cancel_at_period_end, updated_at
        FROM subscriptions
        WHERE user_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "provider": _row_get(row, "provider"),
        "provider_subscription_id": _row_get(row, "provider_subscription_id"),
        "tier": _row_get(row, "tier"),
        "status": _row_get(row, "status"),
        "billing_period": _row_get(row, "billing_period"),
        "current_period_end": _row_get(row, "current_period_end"),
        "cancel_at_period_end": bool(_row_get(row, "cancel_at_period_end")),
        "updated_at": _row_get(row, "updated_at"),
    }


def _serialise_admin_user(conn, row) -> dict[str, object]:
    user_id = int(_row_get(row, "id"))
    entitlement = resolve_user_entitlement(conn, user_id)
    usage = get_user_usage_summary(conn, user_id)
    password_auth_enabled = _row_get(row, "password_auth_enabled")
    return {
        "id": user_id,
        "username": _row_get(row, "username") or "",
        "email": _row_get(row, "email") or "",
        "display_name": _row_get(row, "display_name") or "",
        "first_name": _row_get(row, "first_name") or "",
        "last_name": _row_get(row, "last_name") or "",
        "registered_at": _row_get(row, "registered_at"),
        "account_status": _row_get(row, "account_status") or "active",
        "auth_methods": _auth_methods_for_user(conn, user_id, password_auth_enabled),
        "entitlement": entitlement,
        "usage": usage,
        "subscription": _current_subscription_for_user(conn, user_id),
    }


def _user_label(row) -> str:
    if row is None:
        return "Unknown user"
    return (
        _row_get(row, "display_name")
        or " ".join(
            part for part in [
                str(_row_get(row, "first_name") or "").strip(),
                str(_row_get(row, "last_name") or "").strip(),
            ] if part
        )
        or _row_get(row, "username")
        or _row_get(row, "email")
        or f"User {_row_get(row, 'id')}"
    )


def _record_admin_audit(
    conn,
    *,
    actor_user_id: int,
    action: str,
    resource_type: str,
    resource_id: object | None = None,
    target_user_id: int | None = None,
    outcome: str = "success",
    metadata: dict[str, object] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO admin_audit_events (
            actor_user_id, target_user_id, action, resource_type,
            resource_id, outcome, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            actor_user_id,
            target_user_id,
            action[:120],
            resource_type[:80],
            None if resource_id is None else str(resource_id)[:120],
            outcome,
            json.dumps(metadata or {}, separators=(",", ":")),
        ),
    )


def _serialise_admin_audit_event(row) -> dict[str, object]:
    metadata_raw = _row_get(row, "metadata_json") or "{}"
    try:
        metadata = json.loads(metadata_raw)
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    return {
        "id": int(_row_get(row, "id")),
        "actor_user_id": _row_get(row, "actor_user_id"),
        "actor_name": _user_label({
            "id": _row_get(row, "actor_user_id"),
            "display_name": _row_get(row, "actor_display_name"),
            "first_name": _row_get(row, "actor_first_name"),
            "last_name": _row_get(row, "actor_last_name"),
            "username": _row_get(row, "actor_username"),
            "email": _row_get(row, "actor_email"),
        }),
        "target_user_id": _row_get(row, "target_user_id"),
        "target_name": _user_label({
            "id": _row_get(row, "target_user_id"),
            "display_name": _row_get(row, "target_display_name"),
            "first_name": _row_get(row, "target_first_name"),
            "last_name": _row_get(row, "target_last_name"),
            "username": _row_get(row, "target_username"),
            "email": _row_get(row, "target_email"),
        }) if _row_get(row, "target_user_id") is not None else None,
        "action": _row_get(row, "action"),
        "resource_type": _row_get(row, "resource_type"),
        "resource_id": _row_get(row, "resource_id"),
        "outcome": _row_get(row, "outcome"),
        "metadata": metadata,
        "created_at": _row_get(row, "created_at"),
    }


def _list_admin_audit_events(conn) -> list[dict[str, object]]:
    rows = conn.execute(
        """
        SELECT e.id, e.actor_user_id, e.target_user_id, e.action,
               e.resource_type, e.resource_id, e.outcome, e.metadata_json, e.created_at,
               actor.username AS actor_username,
               actor.email AS actor_email,
               actor.display_name AS actor_display_name,
               actor.first_name AS actor_first_name,
               actor.last_name AS actor_last_name,
               target.username AS target_username,
               target.email AS target_email,
               target.display_name AS target_display_name,
               target.first_name AS target_first_name,
               target.last_name AS target_last_name
        FROM admin_audit_events e
        LEFT JOIN users actor ON actor.id = e.actor_user_id
        LEFT JOIN users target ON target.id = e.target_user_id
        ORDER BY e.created_at DESC, e.id DESC
        LIMIT 100
        """
    ).fetchall()
    return [_serialise_admin_audit_event(row) for row in rows]


def _bounded_int(value: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _current_admin_email(conn, user_id: int) -> str:
    row = conn.execute(
        "SELECT email FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return str(_row_get(row, "email") or "").strip().lower()


def _normalise_test_email_recipient(raw_email: object, fallback_email: str) -> str:
    email = str(raw_email or fallback_email or "").strip().lower()
    if not email:
        raise ValueError("Add an email address to receive the test message.")
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Use a valid email address for the test message.")
    return email


def _list_admin_users(conn, *, search: str = "", tier: str = "", status: str = "", page: int = 1) -> dict[str, object]:
    user_columns = _table_columns(conn, "users")
    registered_expr = "registered_at" if "registered_at" in user_columns else "NULL AS registered_at"
    account_status_expr = (
        "account_status"
        if "account_status" in user_columns
        else "'active' AS account_status"
    )
    password_expr = (
        "password_auth_enabled"
        if "password_auth_enabled" in user_columns
        else "1 AS password_auth_enabled"
    )
    search_text = search.strip().lower()
    params: list[object] = []
    where_clauses: list[str] = []
    if search_text:
        like_value = f"%{search_text}%"
        where_clauses.append(
            """
            (
              lower(COALESCE(username, '')) LIKE ?
              OR lower(COALESCE(email, '')) LIKE ?
              OR lower(COALESCE(display_name, '')) LIKE ?
              OR lower(COALESCE(first_name, '')) LIKE ?
              OR lower(COALESCE(last_name, '')) LIKE ?
            )
            """
        )
        params.extend([like_value] * 5)
    where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    page_number = max(1, int(page or 1))
    page_size = 25
    offset = (page_number - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT id, username, email, display_name, first_name, last_name,
               {registered_expr}, {account_status_expr}, {password_expr}
        FROM users
        {where_clause}
        ORDER BY COALESCE({('registered_at' if 'registered_at' in user_columns else 'username')}, '') DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params + [page_size, offset]),
    ).fetchall()
    users = [_serialise_admin_user(conn, row) for row in rows]
    if tier:
        users = [user for user in users if user["entitlement"].get("tier") == tier]
    if status:
        users = [user for user in users if user["entitlement"].get("status") == status]
    return {
        "users": users,
        "page": page_number,
        "page_size": page_size,
        "has_more": len(rows) == page_size,
    }


def _select_admin_user(conn, user_id: int):
    user_columns = _table_columns(conn, "users")
    registered_expr = "registered_at" if "registered_at" in user_columns else "NULL AS registered_at"
    password_expr = (
        "password_auth_enabled"
        if "password_auth_enabled" in user_columns
        else "1 AS password_auth_enabled"
    )
    account_status_expr = (
        "account_status"
        if "account_status" in user_columns
        else "'active' AS account_status"
    )
    return conn.execute(
        f"""
        SELECT id, username, email, display_name, first_name, last_name,
               {registered_expr}, {password_expr}, {account_status_expr}
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


def _overview(conn) -> dict[str, object]:
    config = load_stripe_billing_config()
    total_users = int(_row_get(conn.execute("SELECT COUNT(*) AS total FROM users").fetchone(), "total") or 0)
    manual_overrides = int(
        _row_get(
            conn.execute(
                "SELECT COUNT(*) AS total FROM entitlements WHERE source = 'manual'"
            ).fetchone(),
            "total",
        )
        or 0
    )
    paid_subscriptions = int(
        _row_get(
            conn.execute(
                """
                SELECT COUNT(*) AS total
                FROM subscriptions
                WHERE provider = 'stripe' AND status IN ('active', 'trialing')
                """
            ).fetchone(),
            "total",
        )
        or 0
    )
    published_announcements = int(
        _row_get(
            conn.execute(
                "SELECT COUNT(*) AS total FROM admin_announcements WHERE status = 'published'"
            ).fetchone(),
            "total",
        )
        or 0
    )
    recent_events = conn.execute(
        """
        SELECT provider_event_id, event_type, user_id, processed_at, metadata_json
        FROM billing_events
        ORDER BY processed_at DESC, id DESC
        LIMIT 12
        """
    ).fetchall()
    return {
        "total_users": total_users,
        "manual_overrides": manual_overrides,
        "paid_subscriptions": paid_subscriptions,
        "published_announcements": published_announcements,
        "stripe": {
            "configured": config.configured,
            "checkout_tiers": configured_checkout_tiers(config),
            "checkout_periods": configured_checkout_periods(config),
        },
        "recent_billing_events": [
            {
                "provider_event_id": _row_get(row, "provider_event_id"),
                "event_type": _row_get(row, "event_type"),
                "user_id": _row_get(row, "user_id"),
                "processed_at": _row_get(row, "processed_at"),
                "metadata": json.loads(_row_get(row, "metadata_json") or "{}"),
            }
            for row in recent_events
        ],
    }


def _read_frontend_cookie_only_setting() -> bool | None:
    """Best-effort check for the production frontend auth transport setting.

    Deployed API containers may not include the frontend source tree, so this is
    intentionally nullable rather than a hard dependency.
    """
    frontend_env = (
        Path(current_app.root_path).parent
        / "client"
        / "src"
        / "environments"
        / "environment.prod.ts"
    )
    try:
        content = frontend_env.read_text(encoding="utf-8")
    except OSError:
        return None
    if "cookieOnlyAuth: true" in content:
        return True
    if "cookieOnlyAuth: false" in content:
        return False
    return None


def _process_supervision_status() -> dict[str, bool]:
    server_root = Path(current_app.root_path)
    repo_root = server_root.parent
    return {
        "wsgi_entrypoint": (server_root / "wsgi.py").exists(),
        "gunicorn_config": (server_root / "gunicorn.conf.py").exists(),
        "healthcheck_script": (server_root / "scripts" / "healthcheck.py").exists(),
        "systemd_template": (repo_root / "deploy" / "systemd" / "openmynd-api.service.example").exists(),
        "health_routes": True,
    }


def _readiness_check(
    key: str,
    label: str,
    status: str,
    detail: str,
) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
    }


def _operations_readiness() -> dict[str, object]:
    adapter = _database_adapter()
    database_report = adapter.health_check(write=False)
    media_report = media_storage_health_check(write=False)
    app_environment = (os.getenv("APP_ENV") or "development").strip().lower()
    database_provider = _database_provider()
    runtime_migrations_enabled = bool(
        current_app.config.get("DATABASE_RUNTIME_MIGRATIONS_ENABLED")
    )
    cookie_mode = bool(current_app.config.get("OPENMYND_AUTH_COOKIE_MODE"))
    csrf_protect = bool(current_app.config.get("JWT_COOKIE_CSRF_PROTECT"))
    frontend_cookie_only = _read_frontend_cookie_only_setting()
    rate_limit_storage = str(
        current_app.config.get("RATELIMIT_STORAGE_URI") or "memory://"
    )
    shared_rate_limiting_deferred = _env_flag("OPENMYND_DEFER_SHARED_RATE_LIMITING")
    stripe_config = load_stripe_billing_config()
    process_status = _process_supervision_status()
    email_provider = (os.getenv("EMAIL_PROVIDER") or "console").strip().lower()
    email_from_address = (os.getenv("EMAIL_FROM_ADDRESS") or "").strip()
    smtp_host = (os.getenv("SMTP_HOST") or "").strip()
    registration_email_required = _env_flag("OPENMYND_REQUIRE_REGISTRATION_EMAIL")
    email_delivery_deferred = _env_flag("OPENMYND_DEFER_EMAIL_DELIVERY")
    email_ready = (
        email_provider == "smtp"
        and bool(email_from_address)
        and bool(smtp_host)
        and registration_email_required
    )
    google_client_id_configured = bool((os.getenv("OAUTH_GOOGLE_CLIENT_ID") or "").strip())
    google_client_secret_configured = bool((os.getenv("OAUTH_GOOGLE_CLIENT_SECRET") or "").strip())
    google_redirect_uri = (os.getenv("OAUTH_GOOGLE_REDIRECT_URI") or "").strip()
    google_redirect_configured = bool(google_redirect_uri)
    google_redirect_is_local = any(
        marker in google_redirect_uri
        for marker in ("localhost", "127.0.0.1", "0.0.0.0")
    )
    google_oauth_ready = (
        google_client_id_configured
        and google_client_secret_configured
        and google_redirect_configured
        and (app_environment != "production" or not google_redirect_is_local)
    )
    openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    openai_api_key_configured = _configured_non_placeholder(openai_api_key)
    analysis_model = (os.getenv("OPENAI_MODEL") or "default").strip() or "default"
    chat_model = (os.getenv("CHAT_MODEL") or "default").strip() or "default"
    image_model = (os.getenv("OPENAI_IMAGE_MODEL") or "default").strip() or "default"

    checks = [
        _readiness_check(
            "database",
            "Database reachable",
            "ok" if database_report.get("ok") else "blocked",
            (
                f"{database_provider.title()} responded in {database_report.get('latency_ms')} ms."
                if database_report.get("ok")
                else "Database read check failed. Review server logs and database credentials."
            ),
        ),
        _readiness_check(
            "database_provider",
            "Production database provider",
            "ok" if database_provider != SQLITE_PROVIDER else "warning",
            (
                "Postgres-ready provider is active."
                if database_provider != SQLITE_PROVIDER
                else "SQLite is suitable for local development only unless using a documented fallback."
            ),
        ),
        _readiness_check(
            "media_storage",
            "Media storage",
            "ok" if media_report.get("ok") else "blocked",
            (
                f"{str(media_report.get('backend') or 'media').upper()} media storage is configured."
                if media_report.get("ok")
                else "Media storage check failed. Review local media or R2 configuration."
            ),
        ),
        _readiness_check(
            "runtime_migrations",
            "Runtime migrations",
            "warning" if runtime_migrations_enabled else "ok",
            (
                "Runtime migrations are enabled. Use explicit migration tooling for public production."
                if runtime_migrations_enabled
                else "Runtime migrations are disabled."
            ),
        ),
        _readiness_check(
            "cookie_auth",
            "Cookie session posture",
            "ok" if cookie_mode and csrf_protect else "warning",
            (
                "Cookie auth and CSRF protection are enabled."
                if cookie_mode and csrf_protect
                else "Enable cookie auth and CSRF protection before public production."
            ),
        ),
        _readiness_check(
            "frontend_cookie_auth",
            "Frontend token transport",
            "ok" if frontend_cookie_only else "warning",
            (
                "Production frontend is configured for cookie-only auth."
                if frontend_cookie_only
                else "Production frontend cookie-only auth is not confirmed."
            ),
        ),
        _readiness_check(
            "rate_limit_storage",
            "Shared rate-limit storage",
            "ok" if rate_limit_storage != "memory://" else "warning",
            (
                "Rate-limit storage is configured outside process memory."
                if rate_limit_storage != "memory://"
                else "Shared rate limiting is deferred for private/beta storage rehearsal."
                if shared_rate_limiting_deferred
                else "Use Redis or another shared limiter backend for multi-worker production."
            ),
        ),
        _readiness_check(
            "stripe",
            "Stripe checkout",
            "ok" if stripe_config.configured else "warning",
            (
                "Stripe credentials and checkout price IDs are configured."
                if stripe_config.configured
                else "Stripe is not fully configured; paid checkout remains unavailable."
            ),
        ),
        _readiness_check(
            "transactional_email",
            "Transactional email",
            "ok" if email_ready else "warning",
            (
                "SMTP, sender, and registration email verification are configured."
                if email_ready
                else "Email delivery is deferred for private/beta storage rehearsal."
                if email_delivery_deferred
                else "Configure SMTP, sender address, and registration email verification before public launch."
            ),
        ),
        _readiness_check(
            "google_oauth",
            "Google OAuth",
            "ok" if google_oauth_ready else "warning",
            (
                "Google client credentials and redirect URI are configured."
                if google_oauth_ready
                else "Configure Google client ID, secret, and a matching redirect URI."
            ),
        ),
        _readiness_check(
            "ai_provider",
            "AI provider",
            "ok" if openai_api_key_configured else "warning",
            (
                "OpenAI backend key is configured. Model names are visible for operations."
                if openai_api_key_configured
                else "Configure a non-placeholder OPENAI_API_KEY before public AI access."
            ),
        ),
        _readiness_check(
            "security_headers",
            "Security response headers",
            "ok",
            (
                "API responses include frame, referrer, content sniffing, permissions, "
                "and content security headers."
            ),
        ),
        _readiness_check(
            "process_supervision",
            "Process supervision assets",
            "ok" if all(process_status.values()) else "warning",
            (
                "WSGI, healthcheck, and supervision templates are present."
                if all(process_status.values())
                else "One or more process supervision assets are missing."
            ),
        ),
    ]

    return {
        "app": {
            "environment": app_environment,
            "production": app_environment == "production",
            "database_provider": database_provider,
            "runtime_migrations_enabled": runtime_migrations_enabled,
        },
        "database": database_report,
        "media_storage": media_report,
        "auth": {
            "cookie_mode": cookie_mode,
            "csrf_protect": csrf_protect,
            "frontend_cookie_only": frontend_cookie_only,
        },
        "rate_limits": {
            "storage": "shared" if rate_limit_storage != "memory://" else "memory",
            "configured": rate_limit_storage != "memory://",
            "deferred": shared_rate_limiting_deferred,
        },
        "stripe": {
            "configured": stripe_config.configured,
            "checkout_tiers": configured_checkout_tiers(stripe_config),
            "checkout_periods": configured_checkout_periods(stripe_config),
        },
        "email": {
            "provider": email_provider,
            "from_configured": bool(email_from_address),
            "smtp_host_configured": bool(smtp_host),
            "registration_email_required": registration_email_required,
            "deferred": email_delivery_deferred,
            "ready": email_ready,
        },
        "oauth": {
            "google": {
                "client_id_configured": google_client_id_configured,
                "client_secret_configured": google_client_secret_configured,
                "redirect_uri_configured": google_redirect_configured,
                "redirect_uri_local": google_redirect_is_local,
                "ready": google_oauth_ready,
            },
        },
        "ai_provider": {
            "openai_api_key_configured": openai_api_key_configured,
            "analysis_model": analysis_model,
            "chat_model": chat_model,
            "image_model": image_model,
            "ready": openai_api_key_configured,
        },
        "security_headers": {
            "enabled": True,
            "hsts": app_environment == "production",
        },
        "process": process_status,
        "checks": checks,
    }


@admin_bp.route("/admin/overview", methods=["GET"])
@jwt_required()
def admin_overview():
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        seed_default_plan_catalogue(conn)
        return jsonify(_overview(conn)), 200


@admin_bp.route("/admin/operations", methods=["GET"])
@jwt_required()
def admin_operations():
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
    return jsonify(_operations_readiness()), 200


@admin_bp.route("/admin/operations/test-email", methods=["POST"])
@jwt_required()
def admin_send_test_email():
    user_id = _current_user_id()
    payload = request.get_json(silent=True) or {}
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        try:
            recipient = _normalise_test_email_recipient(
                payload.get("to_address"),
                _current_admin_email(conn, user_id),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        try:
            send_transactional_email(
                to_address=recipient,
                subject="OpenMynd email delivery test",
                text_body=(
                    "This is an OpenMynd transactional email test. "
                    "If you received this, the configured email provider can deliver messages."
                ),
                logger=current_app.logger,
            )
            _record_admin_audit(
                conn,
                actor_user_id=user_id,
                action="test_email_sent",
                resource_type="email_delivery",
                metadata={
                    "delivery_provider": os.getenv("EMAIL_PROVIDER") or "console",
                    "recipient_domain": recipient.rsplit("@", maxsplit=1)[-1],
                },
            )
            return jsonify({
                "ok": True,
                "message": "Test email sent.",
                "to_address": recipient,
                "provider": os.getenv("EMAIL_PROVIDER") or "console",
            }), 200
        except EmailDeliveryError as exc:
            _record_admin_audit(
                conn,
                actor_user_id=user_id,
                action="test_email_failed",
                resource_type="email_delivery",
                outcome="failure",
                metadata={
                    "delivery_provider": os.getenv("EMAIL_PROVIDER") or "console",
                    "error": str(exc),
                },
            )
            return jsonify({"error": str(exc)}), 502


@admin_bp.route("/admin/preflight", methods=["GET"])
@jwt_required()
def admin_production_preflight():
    user_id = _current_user_id()
    require_postgres = str(request.args.get("require_postgres") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
    return jsonify(
        build_production_preflight(
            root_path=Path(current_app.root_path),
            require_postgres=require_postgres,
        )
    ), 200


def _bool_arg(name: str) -> bool:
    return str(request.args.get(name) or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _int_arg(name: str, default: int) -> int:
    try:
        parsed = int(str(request.args.get(name) or "").strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _maintenance_path(env_name: str, default: Path) -> Path:
    configured = (os.getenv(env_name) or "").strip()
    return Path(configured).expanduser() if configured else default


def _scrub_maintenance_gate(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in gate.items()
        if key not in {"path", "directory"}
    }


def _scrub_maintenance_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        name: {
            key: value
            for key, value in details.items()
            if key != "path"
        }
        for name, details in evidence.items()
        if isinstance(details, dict)
    }


@admin_bp.route("/admin/maintenance", methods=["GET"])
@jwt_required()
def admin_database_maintenance():
    user_id = _current_user_id()
    require_full = _bool_arg("require_full")
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden

    restore_report_value = (os.getenv("OPENMYND_RESTORE_REPORT") or "").strip()
    report = build_database_maintenance_report(
        backup_summary_dir=_maintenance_path("OPENMYND_BACKUP_SUMMARY_DIR", DEFAULT_BACKUP_DIR),
        sqlite_backup_dir=_maintenance_path("OPENMYND_SQLITE_BACKUP_DIR", DEFAULT_BACKUP_DIR),
        postgres_snapshot_dir=_maintenance_path(
            "OPENMYND_POSTGRES_SNAPSHOT_DIR",
            DEFAULT_SNAPSHOT_DIR,
        ),
        media_backup_dir=_maintenance_path("OPENMYND_MEDIA_BACKUP_DIR", DEFAULT_MEDIA_BACKUP_DIR),
        restore_report=Path(restore_report_value).expanduser() if restore_report_value else None,
        max_age_hours=_int_arg("max_age_hours", DEFAULT_DATABASE_MAINTENANCE_MAX_AGE_HOURS),
        require_backup_bundle=True,
        require_sqlite_backup=True,
        require_postgres_snapshot=require_full,
        require_media_archive=require_full,
        require_restore_rehearsal=require_full,
    )
    return jsonify(
        {
            **report,
            "blockers": [_scrub_maintenance_gate(gate) for gate in report["blockers"]],
            "warnings": [_scrub_maintenance_gate(gate) for gate in report["warnings"]],
            "evidence": _scrub_maintenance_evidence(report["evidence"]),
            "require_full": require_full,
        }
    ), 200


@admin_bp.route("/admin/users", methods=["GET"])
@jwt_required()
def admin_users():
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        return jsonify(
            _list_admin_users(
                conn,
                search=str(request.args.get("search") or ""),
                tier=str(request.args.get("tier") or ""),
                status=str(request.args.get("status") or ""),
                page=int(request.args.get("page") or 1),
            )
        ), 200


@admin_bp.route("/admin/users/<int:target_user_id>/entitlement", methods=["PUT"])
@jwt_required()
def admin_update_user_entitlement(target_user_id: int):
    user_id = _current_user_id()
    payload = request.get_json(silent=True) or {}
    tier = str(payload.get("tier") or "").strip().lower()
    status = str(payload.get("status") or "active").strip().lower()
    valid_until = payload.get("valid_until")
    valid_until_text = str(valid_until).strip() if valid_until not in {None, ""} else None
    if tier not in VALID_TIERS:
        return jsonify({"error": "Choose a valid account tier."}), 400
    if status not in VALID_STATUSES:
        return jsonify({"error": "Choose a valid entitlement status."}), 400
    if target_user_id == user_id and tier != "administrator":
        return jsonify({"error": "You cannot remove your own administrator access."}), 400
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        row = conn.execute(
            "SELECT id, username, email, display_name, first_name, last_name FROM users WHERE id = ?",
            (target_user_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "User not found."}), 404
        previous = resolve_user_entitlement(conn, target_user_id)
        upsert_user_entitlement(
            conn,
            user_id=target_user_id,
            tier=tier,
            source="manual",
            status=status,
            valid_until=valid_until_text,
        )
        _record_admin_audit(
            conn,
            actor_user_id=user_id,
            target_user_id=target_user_id,
            action="user_entitlement_updated",
            resource_type="user_entitlement",
            resource_id=target_user_id,
            metadata={
                "previous_tier": previous.get("tier"),
                "previous_status": previous.get("status"),
                "new_tier": tier,
                "new_status": status,
            },
        )
        return jsonify({"user": _serialise_admin_user(conn, row)}), 200


@admin_bp.route("/admin/users/<int:target_user_id>/access", methods=["PUT"])
@jwt_required()
def admin_update_user_access(target_user_id: int):
    user_id = _current_user_id()
    payload = request.get_json(silent=True) or {}
    account_status = str(payload.get("account_status") or "active").strip().lower()
    if account_status not in ACCOUNT_STATUSES:
        return jsonify({"error": "Choose a valid account access status."}), 400
    if target_user_id == user_id and account_status == "restricted":
        return jsonify({"error": "You cannot restrict your own administrator account."}), 400

    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        _ensure_account_status_column(conn)
        row = _select_admin_user(conn, target_user_id)
        if row is None:
            return jsonify({"error": "User not found."}), 404
        previous_status = _row_get(row, "account_status") or "active"
        conn.execute(
            "UPDATE users SET account_status = ? WHERE id = ?",
            (account_status, target_user_id),
        )
        _record_admin_audit(
            conn,
            actor_user_id=user_id,
            target_user_id=target_user_id,
            action="user_access_updated",
            resource_type="user",
            resource_id=target_user_id,
            metadata={
                "previous_account_status": previous_status,
                "new_account_status": account_status,
            },
        )
        refreshed = _select_admin_user(conn, target_user_id)
        return jsonify({"user": _serialise_admin_user(conn, refreshed)}), 200


@admin_bp.route("/admin/users/<int:target_user_id>", methods=["DELETE"])
@jwt_required()
def admin_delete_user(target_user_id: int):
    user_id = _current_user_id()
    if target_user_id == user_id:
        return jsonify({"error": "You cannot delete your own administrator account."}), 400

    media_storage_keys: set[str] = set()
    deleted_label = f"User {target_user_id}"
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden

        row = _select_admin_user(conn, target_user_id)
        if row is None:
            return jsonify({"error": "User not found."}), 404

        deleted_label = _user_label(row)
        media_storage_keys = collect_user_media_storage_keys(conn, target_user_id)
        _record_admin_audit(
            conn,
            actor_user_id=user_id,
            target_user_id=target_user_id,
            action="user_deleted",
            resource_type="user",
            resource_id=target_user_id,
            metadata={
                "deleted_user": deleted_label,
                "username": _row_get(row, "username"),
                "email": _row_get(row, "email"),
                "media_assets": len(media_storage_keys),
            },
        )
        delete_user_account_data(conn, target_user_id)

    delete_user_media(media_storage_keys)
    return jsonify(
        {
            "message": f"{deleted_label} and their OpenMynd data were deleted.",
            "deleted_user_id": target_user_id,
        }
    ), 200


@admin_bp.route("/admin/billing/plans", methods=["GET"])
@jwt_required()
def admin_billing_plans():
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        seed_default_plan_catalogue(conn)
        return jsonify({"plans": list_plan_catalogue(conn, include_internal=True)}), 200


@admin_bp.route("/admin/billing/plans/<tier>", methods=["PUT"])
@jwt_required()
def admin_update_billing_plan(tier: str):
    user_id = _current_user_id()
    payload = request.get_json(silent=True) or {}
    payload["tier"] = tier
    try:
        with get_db() as conn:
            forbidden = _forbid_non_admin(conn, user_id)
            if forbidden:
                return forbidden
            plan = upsert_plan(conn, payload)
            _record_admin_audit(
                conn,
                actor_user_id=user_id,
                action="plan_updated",
                resource_type="billing_plan",
                resource_id=tier,
                metadata={
                    "tier": tier,
                    "public_name": plan.get("public_name"),
                    "is_public": plan.get("is_public"),
                    "is_paid": plan.get("is_paid"),
                },
            )
            return jsonify({"plan": plan}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/admin/announcements", methods=["GET"])
@jwt_required()
def admin_list_announcements():
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        return jsonify({"announcements": _list_announcements(conn)}), 200


@admin_bp.route("/admin/announcements", methods=["POST"])
@jwt_required()
def admin_create_announcement():
    user_id = _current_user_id()
    try:
        payload = _announcement_payload(request.get_json(silent=True) or {})
        with get_db() as conn:
            forbidden = _forbid_non_admin(conn, user_id)
            if forbidden:
                return forbidden
            cursor = conn.execute(
                append_returning_id(
                    """
                    INSERT INTO admin_announcements (
                        title, message, severity, placement, status, starts_at,
                        ends_at, timezone, dismissible, created_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _database_provider(),
                ),
                (
                    payload["title"],
                    payload["message"],
                    payload["severity"],
                    payload["placement"],
                    payload["status"],
                    payload["starts_at"],
                    payload["ends_at"],
                    payload["timezone"],
                    payload["dismissible"],
                    user_id,
                ),
            )
            announcement_id = inserted_id(cursor, _database_provider())
            _write_announcement_targets(conn, announcement_id, payload["targets"])
            _record_admin_audit(
                conn,
                actor_user_id=user_id,
                action="announcement_created",
                resource_type="announcement",
                resource_id=announcement_id,
                metadata={
                    "title": payload["title"],
                    "status": payload["status"],
                    "placement": payload["placement"],
                },
            )
            row = _get_announcement(conn, announcement_id)
            return jsonify({
                "announcement": _serialise_announcement(row, _announcement_targets(conn, announcement_id)),
            }), 201
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/admin/announcements/<int:announcement_id>", methods=["PUT"])
@jwt_required()
def admin_update_announcement(announcement_id: int):
    user_id = _current_user_id()
    try:
        payload = _announcement_payload(request.get_json(silent=True) or {})
        with get_db() as conn:
            forbidden = _forbid_non_admin(conn, user_id)
            if forbidden:
                return forbidden
            if _get_announcement(conn, announcement_id) is None:
                return jsonify({"error": "Announcement not found."}), 404
            conn.execute(
                """
                UPDATE admin_announcements
                SET title = ?, message = ?, severity = ?, placement = ?, status = ?,
                    starts_at = ?, ends_at = ?, timezone = ?, dismissible = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    payload["title"],
                    payload["message"],
                    payload["severity"],
                    payload["placement"],
                    payload["status"],
                    payload["starts_at"],
                    payload["ends_at"],
                    payload["timezone"],
                    payload["dismissible"],
                    announcement_id,
                ),
            )
            _write_announcement_targets(conn, announcement_id, payload["targets"])
            _record_admin_audit(
                conn,
                actor_user_id=user_id,
                action="announcement_updated",
                resource_type="announcement",
                resource_id=announcement_id,
                metadata={
                    "title": payload["title"],
                    "status": payload["status"],
                    "placement": payload["placement"],
                },
            )
            row = _get_announcement(conn, announcement_id)
            return jsonify({
                "announcement": _serialise_announcement(row, _announcement_targets(conn, announcement_id)),
            }), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/admin/announcements/<int:announcement_id>/archive", methods=["POST"])
@jwt_required()
def admin_archive_announcement(announcement_id: int):
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        if _get_announcement(conn, announcement_id) is None:
            return jsonify({"error": "Announcement not found."}), 404
        conn.execute(
            """
            UPDATE admin_announcements
            SET status = 'archived', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (announcement_id,),
        )
        _record_admin_audit(
            conn,
            actor_user_id=user_id,
            action="announcement_archived",
            resource_type="announcement",
            resource_id=announcement_id,
        )
        row = _get_announcement(conn, announcement_id)
        return jsonify({
            "announcement": _serialise_announcement(row, _announcement_targets(conn, announcement_id)),
        }), 200


@admin_bp.route("/admin/audit", methods=["GET"])
@jwt_required()
def admin_audit_events():
    user_id = _current_user_id()
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        return jsonify({"events": _list_admin_audit_events(conn)}), 200


@admin_bp.route("/admin/security", methods=["GET"])
@jwt_required()
def admin_security_audit_report():
    user_id = _current_user_id()
    days = _bounded_int(request.args.get("days"), default=30, minimum=1, maximum=180)
    limit = _bounded_int(request.args.get("limit"), default=50, minimum=1, maximum=200)
    event_type = str(request.args.get("event_type") or "").strip().lower() or None
    outcome = str(request.args.get("outcome") or "").strip().lower() or None
    target_user_id = request.args.get("user_id")
    filtered_user_id = (
        _bounded_int(target_user_id, default=0, minimum=1, maximum=2_147_483_647)
        if target_user_id
        else None
    )
    with get_db() as conn:
        forbidden = _forbid_non_admin(conn, user_id)
        if forbidden:
            return forbidden
        return jsonify(
            build_security_audit_report(
                conn,
                database_provider=_database_provider(),
                days=days,
                limit=limit,
                event_type=event_type,
                outcome=outcome,
                user_id=filtered_user_id,
            )
        ), 200


@admin_bp.route("/announcements/active", methods=["GET"])
@jwt_required()
def active_announcements():
    user_id = _current_user_id()
    with get_db() as conn:
        return jsonify({"announcements": _active_announcements_for_user(conn, user_id)}), 200


@admin_bp.route("/announcements/<int:announcement_id>/read", methods=["POST"])
@jwt_required()
def read_announcement(announcement_id: int):
    user_id = _current_user_id()
    with get_db() as conn:
        if _get_announcement(conn, announcement_id) is None:
            return jsonify({"error": "Announcement not found."}), 404
        _touch_announcement_state(conn, announcement_id, user_id, "read_at")
        return jsonify({"ok": True}), 200


@admin_bp.route("/announcements/<int:announcement_id>/dismiss", methods=["POST"])
@jwt_required()
def dismiss_announcement(announcement_id: int):
    user_id = _current_user_id()
    with get_db() as conn:
        row = _get_announcement(conn, announcement_id)
        if row is None:
            return jsonify({"error": "Announcement not found."}), 404
        if not bool(_row_get(row, "dismissible")):
            return jsonify({"error": "This announcement cannot be dismissed."}), 400
        _touch_announcement_state(conn, announcement_id, user_id, "read_at")
        _touch_announcement_state(conn, announcement_id, user_id, "dismissed_at")
        return jsonify({"ok": True}), 200

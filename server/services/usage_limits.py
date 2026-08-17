"""Plan-aware usage accounting for billable or capacity-sensitive features."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from services.billing_entitlements import resolve_user_entitlement
from services.plan_catalogue import AI_ANALYSIS_LIMIT_KEY, get_plan


AI_ANALYSIS_EVENT = "ai_analysis"
AI_CHAT_EVENT = "ai_chat"
AI_IMAGE_EVENT = "ai_image"
OCR_PAGE_EVENT = "ocr_page"
TRANSCRIPTION_MINUTE_EVENT = "transcription_minute"
EVENT_LIMIT_KEYS = {
    AI_ANALYSIS_EVENT: AI_ANALYSIS_LIMIT_KEY,
    AI_CHAT_EVENT: "ai_chat_monthly",
    AI_IMAGE_EVENT: "ai_images_monthly",
    OCR_PAGE_EVENT: "ocr_pages_monthly",
    TRANSCRIPTION_MINUTE_EVENT: "transcription_minutes_monthly",
}
FALLBACK_PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "storage_mb": 250,
        AI_ANALYSIS_LIMIT_KEY: 10,
        "ai_chat_monthly": 10,
        "ai_images_monthly": 0,
        "ocr_pages_monthly": 5,
        "transcription_minutes_monthly": 0,
    },
    "personal": {
        "storage_mb": 2048,
        AI_ANALYSIS_LIMIT_KEY: 250,
        "ai_chat_monthly": 150,
        "ai_images_monthly": 10,
        "ocr_pages_monthly": 100,
        "transcription_minutes_monthly": 30,
    },
    "plus": {
        "storage_mb": 10240,
        AI_ANALYSIS_LIMIT_KEY: 1000,
        "ai_chat_monthly": 600,
        "ai_images_monthly": 40,
        "ocr_pages_monthly": 500,
        "transcription_minutes_monthly": 180,
    },
    "therapeutic": {
        "storage_mb": 10240,
        AI_ANALYSIS_LIMIT_KEY: 1000,
        "ai_chat_monthly": 600,
        "ai_images_monthly": 40,
        "ocr_pages_monthly": 500,
        "transcription_minutes_monthly": 180,
    },
    "lifetime": {
        "storage_mb": 10240,
        AI_ANALYSIS_LIMIT_KEY: 1000,
        "ai_chat_monthly": 600,
        "ai_images_monthly": 40,
        "ocr_pages_monthly": 500,
        "transcription_minutes_monthly": 180,
    },
    "complimentary": {
        "storage_mb": 10240,
        AI_ANALYSIS_LIMIT_KEY: 1000,
        "ai_chat_monthly": 600,
        "ai_images_monthly": 40,
        "ocr_pages_monthly": 500,
        "transcription_minutes_monthly": 180,
    },
    "administrator": {
        "storage_mb": None,
        AI_ANALYSIS_LIMIT_KEY: None,
        "ai_chat_monthly": None,
        "ai_images_monthly": None,
        "ocr_pages_monthly": None,
        "transcription_minutes_monthly": None,
    },
}


@dataclass
class UsageLimitExceeded(Exception):
    summary: dict[str, Any]


def month_window_start(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def get_plan_limits(conn, tier: str | None) -> dict[str, int | None]:
    normalized = str(tier or "free").strip().lower()
    fallback = dict(FALLBACK_PLAN_LIMITS.get(normalized, FALLBACK_PLAN_LIMITS["free"]))
    try:
        plan = get_plan(conn, normalized)
    except Exception:
        return fallback
    quotas = plan.get("quotas") if isinstance(plan, dict) else {}
    if not isinstance(quotas, dict):
        return fallback
    limits: dict[str, int | None] = {}
    for limit_key, fallback_value in fallback.items():
        value = quotas.get(limit_key, fallback_value)
        if value is None:
            limits[limit_key] = None
            continue
        try:
            limits[limit_key] = max(0, int(value))
        except (TypeError, ValueError):
            limits[limit_key] = fallback_value
    return limits


def get_user_usage_summary(conn, user_id: int) -> dict[str, Any]:
    entitlement = resolve_user_entitlement(conn, user_id)
    tier = str(entitlement.get("tier") or "free")
    limits = get_plan_limits(conn, tier)
    window_start = month_window_start()
    usage_payload = {
        event_type: _usage_for_event(
            conn,
            user_id=user_id,
            event_type=event_type,
            limit=limits.get(limit_key),
            window_start=window_start,
        )
        for event_type, limit_key in EVENT_LIMIT_KEYS.items()
    }
    return {
        "plan": tier,
        "window": "month",
        "window_start": window_start,
        "storage": get_user_storage_summary(conn, user_id, limit_mb=limits.get("storage_mb")),
        **usage_payload,
    }


def get_user_storage_summary(
    conn,
    user_id: int,
    *,
    limit_mb: int | None,
) -> dict[str, Any]:
    measured_bytes = _sum_user_asset_bytes(conn, user_id=user_id)
    unmeasured_assets = _count_unmeasured_media_assets(conn, user_id=user_id)
    used_mb = round(measured_bytes / (1024 * 1024), 2)
    remaining_mb = None if limit_mb is None else max(float(limit_mb) - used_mb, 0)
    return {
        "used_bytes": measured_bytes,
        "used_mb": used_mb,
        "limit_mb": limit_mb,
        "remaining_mb": None if remaining_mb is None else round(remaining_mb, 2),
        "unlimited": limit_mb is None,
        "measured_assets": _count_measured_assets(conn, user_id=user_id),
        "unmeasured_assets": unmeasured_assets,
        "estimated": unmeasured_assets > 0,
    }


def _usage_for_event(
    conn,
    *,
    user_id: int,
    event_type: str,
    limit: int | None,
    window_start: str,
) -> dict[str, Any]:
    used = count_usage_events(
        conn,
        user_id=user_id,
        event_type=event_type,
        since=window_start,
    )
    return {
        "used": used,
        "limit": limit,
        "remaining": None if limit is None else max(int(limit) - used, 0),
        "unlimited": limit is None,
    }


def enforce_usage_limit(
    conn,
    *,
    user_id: int,
    event_type: str,
    units: int = 1,
) -> dict[str, Any]:
    if event_type not in EVENT_LIMIT_KEYS:
        raise ValueError("Unsupported usage event type")
    if units < 1:
        raise ValueError("Usage units must be positive")
    summary = get_user_usage_summary(conn, user_id)
    usage = summary[event_type]
    limit = usage["limit"]
    if limit is not None and int(usage["used"]) + units > int(limit):
        raise UsageLimitExceeded(summary)
    return summary


def enforce_storage_limit(
    conn,
    *,
    user_id: int,
    incoming_bytes: int,
) -> dict[str, Any]:
    if incoming_bytes < 0:
        raise ValueError("Incoming storage bytes must not be negative")
    summary = get_user_usage_summary(conn, user_id)
    storage = summary["storage"]
    limit_mb = storage["limit_mb"]
    if limit_mb is None:
        return summary
    limit_bytes = int(limit_mb) * 1024 * 1024
    if int(storage["used_bytes"] or 0) + incoming_bytes > limit_bytes:
        raise UsageLimitExceeded(summary)
    return summary


def record_usage_event(
    conn,
    *,
    user_id: int,
    event_type: str,
    units: int = 1,
    metadata: dict[str, Any] | None = None,
) -> None:
    if event_type not in EVENT_LIMIT_KEYS:
        raise ValueError("Unsupported usage event type")
    if units < 1:
        raise ValueError("Usage units must be positive")
    conn.execute(
        """
        INSERT INTO usage_events (user_id, event_type, units, metadata_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            event_type,
            units,
            json.dumps(_safe_metadata(metadata or {}), ensure_ascii=False, sort_keys=True),
        ),
    )


def count_usage_events(conn, *, user_id: int, event_type: str, since: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(units), 0) AS total
        FROM usage_events
        WHERE user_id = ? AND event_type = ? AND created_at >= ?
        """,
        (user_id, event_type, since),
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row["total"] or 0)
    except (KeyError, TypeError, IndexError):
        return int(row[0] or 0)


def _sum_user_asset_bytes(conn, *, user_id: int) -> int:
    try:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(file_size_bytes), 0) AS total
            FROM entry_assets
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    except Exception:  # noqa: BLE001
        return 0
    if row is None:
        return 0
    try:
        return int(row["total"] or 0)
    except (KeyError, TypeError, IndexError):
        return int(row[0] or 0)


def _count_measured_assets(conn, *, user_id: int) -> int:
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM entry_assets
            WHERE user_id = ? AND COALESCE(file_size_bytes, 0) > 0
            """,
            (user_id,),
        ).fetchone()
    except Exception:  # noqa: BLE001
        return 0
    if row is None:
        return 0
    try:
        return int(row["total"] or 0)
    except (KeyError, TypeError, IndexError):
        return int(row[0] or 0)


def _count_unmeasured_media_assets(conn, *, user_id: int) -> int:
    total = 0
    total += _count_storage_key_rows(
        conn,
        "dailydiary_entries",
        "image_storage_key",
        user_id=user_id,
    )
    total += _count_storage_key_rows(
        conn,
        "dreamdiary_entries",
        "image_storage_key",
        user_id=user_id,
    )
    total += _count_storage_key_rows(
        conn,
        "important_days",
        "image_storage_key",
        user_id=user_id,
    )
    total += _count_storage_key_rows(
        conn,
        "users",
        "profile_picture_storage_key",
        user_id=user_id,
        user_column="id",
    )
    return total


def _count_storage_key_rows(
    conn,
    table_name: str,
    column_name: str,
    *,
    user_id: int,
    user_column: str = "user_id",
) -> int:
    if not table_name.replace("_", "").isalnum() or not column_name.replace("_", "").isalnum():
        return 0
    if not user_column.replace("_", "").isalnum():
        return 0
    try:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM {table_name}
            WHERE {user_column} = ? AND {column_name} IS NOT NULL AND {column_name} != ''
            """,
            (user_id,),
        ).fetchone()
    except Exception:  # noqa: BLE001
        return 0
    if row is None:
        return 0
    try:
        return int(row["total"] or 0)
    except (KeyError, TypeError, IndexError):
        return int(row[0] or 0)


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, str | int | bool | None]:
    safe: dict[str, str | int | bool | None] = {}
    for raw_key, raw_value in list(metadata.items())[:8]:
        key = str(raw_key or "").strip().lower()
        if not key.replace("_", "").isalnum():
            continue
        if raw_value is None or isinstance(raw_value, bool):
            safe[key] = raw_value
            continue
        if isinstance(raw_value, int):
            safe[key] = raw_value
            continue
        safe[key] = str(raw_value)[:80]
    return safe

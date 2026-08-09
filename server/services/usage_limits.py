"""Plan-aware usage accounting for billable or capacity-sensitive features."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from services.billing_entitlements import resolve_user_entitlement
from services.plan_catalogue import AI_ANALYSIS_LIMIT_KEY, get_plan


AI_ANALYSIS_EVENT = "ai_analysis"
FALLBACK_PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {AI_ANALYSIS_LIMIT_KEY: 10},
    "personal": {AI_ANALYSIS_LIMIT_KEY: 250},
    "plus": {AI_ANALYSIS_LIMIT_KEY: 1000},
    "therapeutic": {AI_ANALYSIS_LIMIT_KEY: 1000},
    "lifetime": {AI_ANALYSIS_LIMIT_KEY: 1000},
    "complimentary": {AI_ANALYSIS_LIMIT_KEY: 1000},
    "administrator": {AI_ANALYSIS_LIMIT_KEY: None},
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
    value = quotas.get(AI_ANALYSIS_LIMIT_KEY, fallback[AI_ANALYSIS_LIMIT_KEY])
    if value is None:
        return {AI_ANALYSIS_LIMIT_KEY: None}
    try:
        return {AI_ANALYSIS_LIMIT_KEY: max(0, int(value))}
    except (TypeError, ValueError):
        return fallback


def get_user_usage_summary(conn, user_id: int) -> dict[str, Any]:
    entitlement = resolve_user_entitlement(conn, user_id)
    tier = str(entitlement.get("tier") or "free")
    limits = get_plan_limits(conn, tier)
    ai_limit = limits[AI_ANALYSIS_LIMIT_KEY]
    window_start = month_window_start()
    used = count_usage_events(
        conn,
        user_id=user_id,
        event_type=AI_ANALYSIS_EVENT,
        since=window_start,
    )
    return {
        "plan": tier,
        "window": "month",
        "window_start": window_start,
        "ai_analysis": {
            "used": used,
            "limit": ai_limit,
            "remaining": None if ai_limit is None else max(int(ai_limit) - used, 0),
            "unlimited": ai_limit is None,
        },
    }


def enforce_usage_limit(conn, *, user_id: int, event_type: str) -> dict[str, Any]:
    if event_type != AI_ANALYSIS_EVENT:
        raise ValueError("Unsupported usage event type")
    summary = get_user_usage_summary(conn, user_id)
    usage = summary["ai_analysis"]
    limit = usage["limit"]
    if limit is not None and int(usage["used"]) >= int(limit):
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
    if event_type != AI_ANALYSIS_EVENT:
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

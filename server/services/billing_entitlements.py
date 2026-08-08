"""OpenMynd-owned billing entitlement helpers.

Stripe or any future payment provider should update these local records. Product code
should read entitlements here rather than depending on provider product or price names.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


VALID_TIERS = {
    "free",
    "personal",
    "plus",
    "therapeutic",
    "lifetime",
    "complimentary",
    "administrator",
}
VALID_SOURCES = {"system", "stripe", "manual"}
VALID_STATUSES = {"active", "inactive", "past_due", "cancelled", "expired"}
ACTIVE_STATUS = "active"
DEFAULT_ENTITLEMENT = {
    "tier": "free",
    "source": "system",
    "status": ACTIVE_STATUS,
    "valid_until": None,
    "is_default": True,
    "is_active": True,
}


def _row_get(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, None)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_valid_until_active(valid_until: Any, *, now: datetime | None = None) -> bool:
    parsed = _parse_timestamp(valid_until)
    if parsed is None:
        return True
    return parsed >= (now or datetime.now(timezone.utc))


def _validate_choice(value: str, allowed: set[str], *, field_name: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in allowed:
        raise ValueError(f"Unsupported {field_name}: {value}")
    return normalized


def resolve_user_entitlement(conn, user_id: int) -> dict[str, Any]:
    """Return the current product entitlement for a user.

    Missing, inactive, cancelled, expired, or time-expired rows resolve to the safe
    default `free` tier. The stored row remains unchanged so webhook/audit processing can
    preserve provider history.
    """
    row = conn.execute(
        """
        SELECT tier, source, status, valid_until, updated_at
        FROM entitlements
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        return dict(DEFAULT_ENTITLEMENT)

    tier = str(_row_get(row, "tier") or "free")
    source = str(_row_get(row, "source") or "system")
    status = str(_row_get(row, "status") or "inactive")
    valid_until = _row_get(row, "valid_until")
    is_active = status == ACTIVE_STATUS and _is_valid_until_active(valid_until)
    if not is_active:
        return {
            **DEFAULT_ENTITLEMENT,
            "is_default": True,
            "stored_tier": tier,
            "stored_status": status,
            "stored_source": source,
            "valid_until": valid_until,
        }

    return {
        "tier": tier,
        "source": source,
        "status": status,
        "valid_until": valid_until,
        "updated_at": _row_get(row, "updated_at"),
        "is_default": False,
        "is_active": True,
    }


def upsert_user_entitlement(
    conn,
    *,
    user_id: int,
    tier: str,
    source: str,
    status: str = ACTIVE_STATUS,
    valid_until: str | None = None,
) -> dict[str, Any]:
    """Create or update the user's local entitlement row."""
    tier = _validate_choice(tier, VALID_TIERS, field_name="tier")
    source = _validate_choice(source, VALID_SOURCES, field_name="source")
    status = _validate_choice(status, VALID_STATUSES, field_name="status")
    conn.execute(
        """
        INSERT INTO entitlements (user_id, tier, source, status, valid_until)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            tier = excluded.tier,
            source = excluded.source,
            status = excluded.status,
            valid_until = excluded.valid_until,
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, tier, source, status, valid_until),
    )
    return resolve_user_entitlement(conn, user_id)


def ensure_default_entitlement(conn, user_id: int) -> dict[str, Any]:
    """Persist a default free entitlement if none exists and return the resolved value."""
    conn.execute(
        """
        INSERT INTO entitlements (user_id, tier, source, status)
        VALUES (?, 'free', 'system', 'active')
        ON CONFLICT(user_id) DO NOTHING
        """,
        (user_id,),
    )
    return resolve_user_entitlement(conn, user_id)


def record_billing_event(
    conn,
    *,
    provider: str,
    provider_event_id: str,
    event_type: str,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Record a provider event once.

    Returns True when a new event row was inserted and False for a duplicate. This is the
    idempotency seam future Stripe webhook processing should use.
    """
    provider = _validate_choice(provider, {"stripe", "manual"}, field_name="provider")
    provider_event_id = (provider_event_id or "").strip()
    event_type = (event_type or "").strip()
    if not provider_event_id:
        raise ValueError("provider_event_id is required")
    if not event_type:
        raise ValueError("event_type is required")
    cursor = conn.execute(
        """
        INSERT INTO billing_events (
            provider,
            provider_event_id,
            event_type,
            user_id,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(provider, provider_event_id) DO NOTHING
        """,
        (
            provider,
            provider_event_id,
            event_type,
            user_id,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    return int(getattr(cursor, "rowcount", 0) or 0) > 0

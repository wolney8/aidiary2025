"""Privacy-aware security audit event persistence."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from typing import Any

from services.sql_compat import adapt_placeholders


EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,80}$")
OUTCOME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
MAX_METADATA_KEYS = 12
MAX_METADATA_VALUE_LENGTH = 120


def record_security_event(
    conn,
    *,
    database_provider: str,
    secret: str,
    user_id: int | None,
    event_type: str,
    outcome: str = "success",
    request_obj: Any = None,
    metadata: Mapping[str, Any] | None = None,
    logger: Any = None,
) -> bool:
    """Persist a low-sensitivity security event.

    The audit record intentionally stores request identifiers as keyed hashes
    rather than raw IP/user-agent values. Callers should pass only categorical
    metadata, never emails, tokens, passwords, prompts, diary text, or filenames.
    """
    try:
        safe_event_type = _normalise_event_type(event_type)
        safe_outcome = _normalise_outcome(outcome)
        ip_hash = _hash_optional_value(_client_ip(request_obj), secret)
        user_agent_hash = _hash_optional_value(_user_agent(request_obj), secret)
        metadata_json = json.dumps(
            _normalise_metadata(metadata or {}),
            ensure_ascii=False,
            sort_keys=True,
        )

        conn.execute(
            adapt_placeholders(
                """
                INSERT INTO security_audit_events (
                    user_id, event_type, outcome, ip_hash, user_agent_hash,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                database_provider,
            ),
            (
                user_id,
                safe_event_type,
                safe_outcome,
                ip_hash,
                user_agent_hash,
                metadata_json,
            ),
        )
        return True
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning("Security audit event could not be persisted: %s", exc)
        return False


def _normalise_event_type(value: str) -> str:
    event_type = str(value or "").strip().lower()
    if not EVENT_TYPE_PATTERN.fullmatch(event_type):
        raise ValueError("Invalid security audit event type")
    return event_type


def _normalise_outcome(value: str) -> str:
    outcome = str(value or "").strip().lower()
    if not OUTCOME_PATTERN.fullmatch(outcome):
        raise ValueError("Invalid security audit outcome")
    return outcome


def _client_ip(request_obj: Any) -> str:
    if request_obj is None:
        return ""
    forwarded_for = str(request_obj.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return str(getattr(request_obj, "remote_addr", "") or "").strip()


def _user_agent(request_obj: Any) -> str:
    if request_obj is None:
        return ""
    return str(request_obj.headers.get("User-Agent") or "").strip()


def _hash_optional_value(value: str, secret: str) -> str | None:
    value = str(value or "").strip()
    if not value:
        return None
    key = str(secret or "openmynd-audit").encode("utf-8")
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _normalise_metadata(metadata: Mapping[str, Any]) -> dict[str, str | int | bool | None]:
    normalised: dict[str, str | int | bool | None] = {}
    for raw_key, raw_value in list(metadata.items())[:MAX_METADATA_KEYS]:
        key = str(raw_key or "").strip().lower()
        if not EVENT_TYPE_PATTERN.fullmatch(key):
            continue
        if raw_value is None or isinstance(raw_value, bool):
            normalised[key] = raw_value
            continue
        if isinstance(raw_value, int):
            normalised[key] = raw_value
            continue
        value = str(raw_value).strip()
        normalised[key] = value[:MAX_METADATA_VALUE_LENGTH]
    return normalised

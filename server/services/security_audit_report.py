"""Security audit reporting helpers for operator review."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from services.sql_compat import adapt_placeholders


MAX_REPORT_LIMIT = 500


def build_security_audit_report(
    conn,
    *,
    database_provider: str,
    days: int = 30,
    limit: int = 50,
    event_type: str | None = None,
    outcome: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Return a privacy-safe report over `security_audit_events`."""
    if not _table_exists(conn, database_provider, "security_audit_events"):
        return {
            "generated_at": _utc_now(),
            "available": False,
            "message": "security_audit_events table does not exist.",
            "filters": _filters(days, limit, event_type, outcome, user_id),
            "total_events": 0,
            "events_by_type": [],
            "events_by_outcome": [],
            "recent_events": [],
        }

    safe_limit = max(1, min(int(limit or 50), MAX_REPORT_LIMIT))
    where_sql, params = _where_clause(
        days=days,
        event_type=event_type,
        outcome=outcome,
        user_id=user_id,
    )

    total_events = int(
        conn.execute(
            adapt_placeholders(
                f"SELECT COUNT(*) AS total FROM security_audit_events {where_sql}",
                database_provider,
            ),
            tuple(params),
        ).fetchone()["total"]
        or 0
    )
    events_by_type = [
        {
            "event_type": row["event_type"],
            "outcome": row["outcome"],
            "count": int(row["total"] or 0),
        }
        for row in conn.execute(
            adapt_placeholders(
                f"""
                SELECT event_type, outcome, COUNT(*) AS total
                FROM security_audit_events
                {where_sql}
                GROUP BY event_type, outcome
                ORDER BY total DESC, event_type ASC, outcome ASC
                """,
                database_provider,
            ),
            tuple(params),
        ).fetchall()
    ]
    events_by_outcome = [
        {
            "outcome": row["outcome"],
            "count": int(row["total"] or 0),
        }
        for row in conn.execute(
            adapt_placeholders(
                f"""
                SELECT outcome, COUNT(*) AS total
                FROM security_audit_events
                {where_sql}
                GROUP BY outcome
                ORDER BY total DESC, outcome ASC
                """,
                database_provider,
            ),
            tuple(params),
        ).fetchall()
    ]
    recent_params = [*params, safe_limit]
    recent_events = [
        _serialise_event(row)
        for row in conn.execute(
            adapt_placeholders(
                f"""
                SELECT id, user_id, event_type, outcome, metadata_json, created_at
                FROM security_audit_events
                {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                database_provider,
            ),
            tuple(recent_params),
        ).fetchall()
    ]

    return {
        "generated_at": _utc_now(),
        "available": True,
        "filters": _filters(days, safe_limit, event_type, outcome, user_id),
        "total_events": total_events,
        "events_by_type": events_by_type,
        "events_by_outcome": events_by_outcome,
        "recent_events": recent_events,
    }


def format_security_audit_report(report: dict[str, Any]) -> str:
    """Format a compact human-readable report for terminal use."""
    if not report.get("available"):
        return str(report.get("message") or "Security audit report is unavailable.")

    lines = [
        "Security audit report",
        f"Generated: {report['generated_at']}",
        f"Total events: {report['total_events']}",
        "",
        "By event type:",
    ]
    if report["events_by_type"]:
        lines.extend(
            f"- {row['event_type']} / {row['outcome']}: {row['count']}"
            for row in report["events_by_type"]
        )
    else:
        lines.append("- No matching events")

    lines.append("")
    lines.append("Recent events:")
    if report["recent_events"]:
        lines.extend(
            (
                f"- #{row['id']} {row['created_at']} "
                f"user={row['user_id'] or '-'} {row['event_type']} "
                f"({row['outcome']}) metadata={row['metadata']}"
            )
            for row in report["recent_events"]
        )
    else:
        lines.append("- No matching events")

    return "\n".join(lines)


def _where_clause(
    *,
    days: int,
    event_type: str | None,
    outcome: str | None,
    user_id: int | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if days and int(days) > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
        clauses.append("created_at >= ?")
        params.append(cutoff.strftime("%Y-%m-%d %H:%M:%S"))
    if event_type:
        clauses.append("event_type = ?")
        params.append(str(event_type).strip().lower())
    if outcome:
        clauses.append("outcome = ?")
        params.append(str(outcome).strip().lower())
    if user_id is not None:
        clauses.append("user_id = ?")
        params.append(int(user_id))
    if not clauses:
        return "", []
    return f"WHERE {' AND '.join(clauses)}", params


def _table_exists(conn, database_provider: str, table_name: str) -> bool:
    try:
        if database_provider == "sqlite":
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                    (table_name,),
                ).fetchone()
                is not None
            )
        return (
            conn.execute(
                adapt_placeholders(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = ?
                    """,
                    database_provider,
                ),
                (table_name,),
            ).fetchone()
            is not None
        )
    except Exception:
        return False


def _serialise_event(row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "user_id": row["user_id"],
        "event_type": row["event_type"],
        "outcome": row["outcome"],
        "created_at": row["created_at"],
        "metadata": _metadata(row["metadata_json"]),
    }


def _metadata(value: str | None) -> dict[str, Any]:
    try:
        metadata = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def _filters(
    days: int,
    limit: int,
    event_type: str | None,
    outcome: str | None,
    user_id: int | None,
) -> dict[str, Any]:
    return {
        "days": int(days or 0),
        "limit": int(limit or 0),
        "event_type": event_type,
        "outcome": outcome,
        "user_id": user_id,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

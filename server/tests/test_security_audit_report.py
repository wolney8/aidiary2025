import json
import sqlite3
from datetime import datetime, timedelta, timezone

from services.runtime_migrations import ensure_security_audit_events_table
from services.security_audit import record_security_event
from services.security_audit_report import (
    build_security_audit_report,
    format_security_audit_report,
)


def test_security_audit_report_handles_missing_table(tmp_path):
    db_path = tmp_path / "empty.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        report = build_security_audit_report(
            conn,
            database_provider="sqlite",
        )

    assert report["available"] is False
    assert report["total_events"] == 0
    assert "does not exist" in report["message"]


def test_security_audit_report_summarises_and_filters_events(tmp_path):
    db_path = tmp_path / "audit.db"
    ensure_security_audit_events_table(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=1,
            event_type="login_success",
        )
        record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=1,
            event_type="login_failed",
            outcome="rejected",
            metadata={"reason": "bad_password"},
        )
        record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=2,
            event_type="oauth_callback_success",
            metadata={"provider": "google"},
        )

        report = build_security_audit_report(
            conn,
            database_provider="sqlite",
            days=30,
            limit=2,
            user_id=1,
        )

    assert report["available"] is True
    assert report["total_events"] == 2
    assert report["filters"]["user_id"] == 1
    assert report["events_by_outcome"] == [
        {"outcome": "rejected", "count": 1},
        {"outcome": "success", "count": 1},
    ]
    assert {row["event_type"] for row in report["events_by_type"]} == {
        "login_failed",
        "login_success",
    }
    assert len(report["recent_events"]) == 2
    assert report["recent_events"][0]["metadata"] in (
        {},
        {"reason": "bad_password"},
    )


def test_security_audit_report_respects_days_filter(tmp_path):
    db_path = tmp_path / "audit.db"
    ensure_security_audit_events_table(str(db_path))
    old_created_at = (
        datetime.now(timezone.utc) - timedelta(days=10)
    ).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=1,
            event_type="login_success",
        )
        conn.execute(
            """
            INSERT INTO security_audit_events (
                user_id, event_type, outcome, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (1, "login_failed", "rejected", json.dumps({"reason": "old"}), old_created_at),
        )

        report = build_security_audit_report(
            conn,
            database_provider="sqlite",
            days=1,
        )

    assert report["total_events"] == 1
    assert report["recent_events"][0]["event_type"] == "login_success"


def test_security_audit_report_formats_text_summary(tmp_path):
    db_path = tmp_path / "audit.db"
    ensure_security_audit_events_table(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        record_security_event(
            conn,
            database_provider="sqlite",
            secret="test-secret",
            user_id=1,
            event_type="login_success",
        )
        report = build_security_audit_report(
            conn,
            database_provider="sqlite",
            days=30,
        )

    output = format_security_audit_report(report)

    assert "Security audit report" in output
    assert "login_success / success: 1" in output
    assert "metadata={}" in output

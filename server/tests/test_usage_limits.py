import sqlite3
from datetime import datetime, timezone

import pytest

from services.billing_entitlements import upsert_user_entitlement
from services.runtime_migrations import ensure_billing_tables
from services.usage_limits import (
    AI_ANALYSIS_EVENT,
    AI_IMAGE_EVENT,
    OCR_PAGE_EVENT,
    TRANSCRIPTION_MINUTE_EVENT,
    UsageLimitExceeded,
    enforce_usage_limit,
    get_user_usage_summary,
    month_window_start,
    record_usage_event,
)
from services.plan_catalogue import upsert_plan


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_usage_db(db_path):
    with _connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO users (id, username, password) VALUES (1, 'tester', 'hash')"
        )
    ensure_billing_tables(str(db_path))


def test_month_window_start_uses_database_comparable_timestamp():
    assert (
        month_window_start(datetime(2026, 8, 12, 9, 30, tzinfo=timezone.utc))
        == "2026-08-01 00:00:00"
    )


def test_free_plan_usage_summary_tracks_monthly_ai_limit(tmp_path):
    db_path = tmp_path / "usage.db"
    _create_usage_db(db_path)

    with _connect(db_path) as conn:
        record_usage_event(
            conn,
            user_id=1,
            event_type=AI_ANALYSIS_EVENT,
            metadata={"mode": "daily"},
        )
        summary = get_user_usage_summary(conn, 1)

    assert summary["plan"] == "free"
    assert summary["ai_analysis"]["used"] == 1
    assert summary["ai_analysis"]["limit"] == 10
    assert summary["ai_analysis"]["remaining"] == 9
    assert summary["ai_image"]["limit"] == 0
    assert summary["ocr_page"]["limit"] == 5
    assert summary["transcription_minute"]["limit"] == 0


def test_usage_limit_blocks_when_monthly_limit_is_reached(tmp_path):
    db_path = tmp_path / "usage.db"
    _create_usage_db(db_path)

    with _connect(db_path) as conn:
        for _index in range(10):
            record_usage_event(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)

        with pytest.raises(UsageLimitExceeded) as exc_info:
            enforce_usage_limit(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)

    assert exc_info.value.summary["ai_analysis"]["used"] == 10
    assert exc_info.value.summary["ai_analysis"]["remaining"] == 0


def test_usage_limit_reads_admin_editable_plan_catalogue(tmp_path):
    db_path = tmp_path / "usage.db"
    _create_usage_db(db_path)

    with _connect(db_path) as conn:
        upsert_plan(
            conn,
            {
                "tier": "free",
                "public_name": "Free",
                "quotas": {"ai_analysis_monthly": 2},
                "features": ["Two AI responses"],
                "is_public": True,
                "sort_order": 10,
            },
        )
        record_usage_event(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)
        record_usage_event(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)

        with pytest.raises(UsageLimitExceeded) as exc_info:
            enforce_usage_limit(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)

    assert exc_info.value.summary["ai_analysis"]["limit"] == 2


def test_usage_limit_blocks_zero_allowance_features(tmp_path):
    db_path = tmp_path / "usage.db"
    _create_usage_db(db_path)

    with _connect(db_path) as conn:
        with pytest.raises(UsageLimitExceeded) as image_exc:
            enforce_usage_limit(conn, user_id=1, event_type=AI_IMAGE_EVENT)
        with pytest.raises(UsageLimitExceeded) as transcription_exc:
            enforce_usage_limit(conn, user_id=1, event_type=TRANSCRIPTION_MINUTE_EVENT)

    assert image_exc.value.summary["ai_image"]["limit"] == 0
    assert transcription_exc.value.summary["transcription_minute"]["limit"] == 0


def test_usage_limit_supports_units_for_ocr_pages(tmp_path):
    db_path = tmp_path / "usage.db"
    _create_usage_db(db_path)

    with _connect(db_path) as conn:
        record_usage_event(conn, user_id=1, event_type=OCR_PAGE_EVENT, units=4)
        enforce_usage_limit(conn, user_id=1, event_type=OCR_PAGE_EVENT, units=1)

        with pytest.raises(UsageLimitExceeded) as exc_info:
            enforce_usage_limit(conn, user_id=1, event_type=OCR_PAGE_EVENT, units=2)

    assert exc_info.value.summary["ocr_page"]["used"] == 4
    assert exc_info.value.summary["ocr_page"]["remaining"] == 1


def test_administrator_usage_is_unlimited(tmp_path):
    db_path = tmp_path / "usage.db"
    _create_usage_db(db_path)

    with _connect(db_path) as conn:
        upsert_user_entitlement(
            conn,
            user_id=1,
            tier="administrator",
            source="manual",
        )
        for _index in range(25):
            record_usage_event(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)
        summary = enforce_usage_limit(conn, user_id=1, event_type=AI_ANALYSIS_EVENT)

    assert summary["ai_analysis"]["unlimited"] is True
    assert summary["ai_analysis"]["remaining"] is None

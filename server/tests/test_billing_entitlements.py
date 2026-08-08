import sqlite3

import pytest

from services.account_deletion import delete_user_account_data
from services.billing_entitlements import (
    ensure_default_entitlement,
    record_billing_event,
    resolve_user_entitlement,
    upsert_user_entitlement,
)
from services.runtime_migrations import ensure_billing_tables


def _connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_user(conn, user_id=1):
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
        "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
        (user_id, f"user-{user_id}", "hash"),
    )


def _create_billing_db(db_path):
    with _connect(db_path) as conn:
        _create_user(conn)
    ensure_billing_tables(str(db_path))


def test_missing_entitlement_resolves_to_free_without_provider_dependency(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        entitlement = resolve_user_entitlement(conn, 1)

    assert entitlement["tier"] == "free"
    assert entitlement["source"] == "system"
    assert entitlement["status"] == "active"
    assert entitlement["is_default"] is True
    assert entitlement["is_active"] is True


def test_default_entitlement_can_be_persisted_for_existing_users(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        entitlement = ensure_default_entitlement(conn, 1)
        row_count = conn.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0]

    assert entitlement["tier"] == "free"
    assert row_count == 1


def test_paid_entitlement_resolves_from_openmynd_owned_row(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        entitlement = upsert_user_entitlement(
            conn,
            user_id=1,
            tier="plus",
            source="stripe",
            status="active",
        )

    assert entitlement["tier"] == "plus"
    assert entitlement["source"] == "stripe"
    assert entitlement["is_default"] is False


def test_inactive_or_expired_entitlements_fall_back_to_free(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        inactive = upsert_user_entitlement(
            conn,
            user_id=1,
            tier="personal",
            source="stripe",
            status="cancelled",
        )
        expired = upsert_user_entitlement(
            conn,
            user_id=1,
            tier="plus",
            source="stripe",
            status="active",
            valid_until="2020-01-01T00:00:00Z",
        )

    assert inactive["tier"] == "free"
    assert inactive["stored_tier"] == "personal"
    assert inactive["stored_status"] == "cancelled"
    assert expired["tier"] == "free"
    assert expired["stored_tier"] == "plus"


def test_entitlement_helpers_reject_unknown_values(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        with pytest.raises(ValueError, match="Unsupported tier"):
            upsert_user_entitlement(
                conn,
                user_id=1,
                tier="stripe-price-123",
                source="stripe",
            )


def test_billing_events_are_idempotent_by_provider_event_id(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        first = record_billing_event(
            conn,
            provider="stripe",
            provider_event_id="evt_123",
            event_type="checkout.session.completed",
            user_id=1,
            metadata={"mode": "subscription"},
        )
        second = record_billing_event(
            conn,
            provider="stripe",
            provider_event_id="evt_123",
            event_type="checkout.session.completed",
            user_id=1,
        )
        row_count = conn.execute("SELECT COUNT(*) FROM billing_events").fetchone()[0]

    assert first is True
    assert second is False
    assert row_count == 1


def test_account_deletion_removes_billing_rows(tmp_path):
    db_path = tmp_path / "billing.db"
    _create_billing_db(db_path)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO billing_customers (user_id, provider_customer_id)
            VALUES (1, 'cus_123')
            """
        )
        conn.execute(
            """
            INSERT INTO subscriptions (
                user_id,
                provider_subscription_id,
                tier,
                status
            )
            VALUES (1, 'sub_123', 'plus', 'active')
            """
        )
        upsert_user_entitlement(
            conn,
            user_id=1,
            tier="plus",
            source="stripe",
        )
        record_billing_event(
            conn,
            provider="stripe",
            provider_event_id="evt_123",
            event_type="customer.subscription.created",
            user_id=1,
        )
        conn.execute(
            """
            INSERT INTO usage_events (user_id, event_type, units, metadata_json)
            VALUES (1, 'ai_analysis', 1, '{"mode": "daily"}')
            """
        )

        delete_user_account_data(conn, 1)

        assert conn.execute("SELECT COUNT(*) FROM billing_customers").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM subscriptions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM entitlements").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM billing_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM usage_events").fetchone()[0] == 0

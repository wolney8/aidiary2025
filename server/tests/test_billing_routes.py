import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import tempfile
import time

import pytest
from flask_jwt_extended import create_access_token

from app import create_app


@pytest.fixture
def client(monkeypatch):
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("MEDIA_ROOT", media_root)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_PERSONAL", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_PLUS", raising=False)

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as test_client:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    display_name TEXT,
                    onboarding_completed INTEGER DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                INSERT INTO users (
                    id, username, password, email, first_name, last_name, display_name
                )
                VALUES (1, 'tester', 'hash', 'tester@example.com', 'Test', 'User', 'Tester')
                """
            )
        yield test_client

    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(media_root, ignore_errors=True)


def _headers(app, user_id=1):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}"}


def _stripe_signature(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    signed_at = int(timestamp or time.time())
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{signed_at}.".encode("utf-8") + payload,
        hashlib.sha256,
    ).hexdigest()
    return f"t={signed_at},v1={digest}"


def _post_webhook(client, event, secret="whsec_test"):
    payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
    return client.post(
        "/api/billing/stripe/webhook",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _stripe_signature(payload, secret),
        },
    )


def test_billing_status_defaults_to_free_when_stripe_not_configured(client):
    response = client.get("/api/billing/status", headers=_headers(client.application))

    assert response.status_code == 200
    body = response.get_json()
    assert body["entitlement"]["tier"] == "free"
    assert body["stripe_configured"] is False
    assert body["checkout_tiers"] == []
    assert body["has_billing_customer"] is False


def test_checkout_requires_auth(client):
    response = client.post("/api/billing/checkout-session", json={"tier": "personal"})

    assert response.status_code == 401


def test_checkout_rejects_unconfigured_plan(client):
    response = client.post(
        "/api/billing/checkout-session",
        headers=_headers(client.application),
        json={"tier": "personal"},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "Stripe billing is not configured."


def test_checkout_creates_customer_and_session(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_PERSONAL", "price_personal")
    created_customers = []
    created_sessions = []

    def fake_create_customer(**kwargs):
        created_customers.append(kwargs)
        return {"id": "cus_123"}

    def fake_create_checkout_session(**kwargs):
        created_sessions.append(kwargs)
        return {"url": "https://checkout.stripe.test/session"}

    monkeypatch.setattr("routes.billing.create_stripe_customer", fake_create_customer)
    monkeypatch.setattr("routes.billing.create_checkout_session", fake_create_checkout_session)

    response = client.post(
        "/api/billing/checkout-session",
        headers=_headers(client.application),
        json={"tier": "personal"},
    )

    assert response.status_code == 200
    assert response.get_json()["url"] == "https://checkout.stripe.test/session"
    assert created_customers[0]["email"] == "tester@example.com"
    assert created_customers[0]["name"] == "Test User"
    assert created_sessions[0]["tier"] == "personal"
    assert created_sessions[0]["customer_id"] == "cus_123"

    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT provider_customer_id FROM billing_customers WHERE user_id = 1"
        ).fetchone()
    assert row[0] == "cus_123"


def test_checkout_reuses_existing_customer(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_PRICE_PLUS", "price_plus")
    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO billing_customers (user_id, provider_customer_id)
            VALUES (1, 'cus_existing')
            """
        )

    create_customer = lambda **_kwargs: pytest.fail("customer should be reused")
    created_sessions = []
    monkeypatch.setattr("routes.billing.create_stripe_customer", create_customer)
    monkeypatch.setattr(
        "routes.billing.create_checkout_session",
        lambda **kwargs: created_sessions.append(kwargs) or {"url": "https://checkout.stripe.test/plus"},
    )

    response = client.post(
        "/api/billing/checkout-session",
        headers=_headers(client.application),
        json={"tier": "plus"},
    )

    assert response.status_code == 200
    assert created_sessions[0]["customer_id"] == "cus_existing"


def test_customer_portal_requires_existing_customer(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")

    response = client.post(
        "/api/billing/customer-portal-session",
        headers=_headers(client.application),
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Start a subscription before opening billing management."


def test_customer_portal_returns_stripe_url(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO billing_customers (user_id, provider_customer_id)
            VALUES (1, 'cus_existing')
            """
        )

    monkeypatch.setattr(
        "routes.billing.create_customer_portal_session",
        lambda **kwargs: {"url": "https://billing.stripe.test/session"},
    )

    response = client.post(
        "/api/billing/customer-portal-session",
        headers=_headers(client.application),
    )

    assert response.status_code == 200
    assert response.get_json()["url"] == "https://billing.stripe.test/session"


def test_stripe_webhook_requires_configured_signing_secret(client):
    event = {"id": "evt_missing_secret", "type": "checkout.session.completed", "data": {"object": {}}}
    payload = json.dumps(event).encode("utf-8")

    response = client.post(
        "/api/billing/stripe/webhook",
        data=payload,
        headers={"Stripe-Signature": _stripe_signature(payload, "whsec_test")},
    )

    assert response.status_code == 503


def test_stripe_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    event = {"id": "evt_bad_sig", "type": "checkout.session.completed", "data": {"object": {}}}

    response = client.post(
        "/api/billing/stripe/webhook",
        data=json.dumps(event).encode("utf-8"),
        headers={"Stripe-Signature": "t=123,v1=not-valid"},
    )

    assert response.status_code == 400


def test_checkout_completed_webhook_activates_entitlement(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    event = {
        "id": "evt_checkout_completed",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test_123",
                "object": "checkout.session",
                "customer": "cus_123",
                "subscription": "sub_123",
                "client_reference_id": "1",
                "metadata": {"openmynd_user_id": "1", "tier": "plus"},
            }
        },
    }

    response = _post_webhook(client, event)

    assert response.status_code == 200
    assert response.get_json() == {"received": True, "duplicate": False}

    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        entitlement = conn.execute(
            "SELECT tier, source, status FROM entitlements WHERE user_id = 1"
        ).fetchone()
        subscription = conn.execute(
            """
            SELECT provider_subscription_id, tier, status
            FROM subscriptions
            WHERE user_id = 1
            """
        ).fetchone()
        event_count = conn.execute("SELECT COUNT(*) FROM billing_events").fetchone()[0]

    assert entitlement == ("plus", "stripe", "active")
    assert subscription == ("sub_123", "plus", "active")
    assert event_count == 1


def test_subscription_updated_webhook_maps_price_to_tier(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_PRICE_PLUS", "price_plus")
    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO billing_customers (user_id, provider_customer_id)
            VALUES (1, 'cus_123')
            """
        )
    event = {
        "id": "evt_subscription_updated",
        "type": "customer.subscription.updated",
        "livemode": False,
        "data": {
            "object": {
                "id": "sub_123",
                "object": "subscription",
                "customer": "cus_123",
                "status": "past_due",
                "current_period_start": 1786122000,
                "current_period_end": 1788800400,
                "cancel_at_period_end": True,
                "items": {
                    "data": [
                        {
                            "price": {
                                "id": "price_plus",
                            }
                        }
                    ]
                },
            }
        },
    }

    response = _post_webhook(client, event)

    assert response.status_code == 200
    with sqlite3.connect(db_path) as conn:
        entitlement = conn.execute(
            "SELECT tier, source, status, valid_until FROM entitlements WHERE user_id = 1"
        ).fetchone()
        subscription = conn.execute(
            """
            SELECT tier, status, cancel_at_period_end
            FROM subscriptions
            WHERE provider_subscription_id = 'sub_123'
            """
        ).fetchone()

    assert entitlement[0:3] == ("plus", "stripe", "past_due")
    assert entitlement[3].startswith("2026-09-")
    assert subscription == ("plus", "past_due", 1)


def test_stripe_webhook_duplicate_delivery_is_idempotent(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    event = {
        "id": "evt_duplicate",
        "type": "checkout.session.completed",
        "livemode": False,
        "data": {
            "object": {
                "id": "cs_test_duplicate",
                "object": "checkout.session",
                "customer": "cus_duplicate",
                "subscription": "sub_duplicate",
                "client_reference_id": "1",
                "metadata": {"tier": "personal"},
            }
        },
    }

    first = _post_webhook(client, event)
    second = _post_webhook(client, event)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json() == {"received": True, "duplicate": True}

    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        event_count = conn.execute(
            "SELECT COUNT(*) FROM billing_events WHERE provider_event_id = 'evt_duplicate'"
        ).fetchone()[0]
        subscription_count = conn.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE provider_subscription_id = 'sub_duplicate'"
        ).fetchone()[0]

    assert event_count == 1
    assert subscription_count == 1


def test_invoice_payment_failed_marks_existing_entitlement_past_due(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO billing_customers (user_id, provider_customer_id) VALUES (1, 'cus_123')"
        )
        conn.execute(
            """
            INSERT INTO subscriptions (
                user_id, provider_subscription_id, tier, status
            )
            VALUES (1, 'sub_123', 'plus', 'active')
            """
        )
    event = {
        "id": "evt_invoice_failed",
        "type": "invoice.payment_failed",
        "livemode": False,
        "data": {
            "object": {
                "id": "in_123",
                "object": "invoice",
                "customer": "cus_123",
                "subscription": "sub_123",
            }
        },
    }

    response = _post_webhook(client, event)

    assert response.status_code == 200
    with sqlite3.connect(db_path) as conn:
        entitlement = conn.execute(
            "SELECT tier, source, status FROM entitlements WHERE user_id = 1"
        ).fetchone()
        subscription = conn.execute(
            "SELECT tier, status FROM subscriptions WHERE provider_subscription_id = 'sub_123'"
        ).fetchone()

    assert entitlement == ("plus", "stripe", "past_due")
    assert subscription == ("plus", "past_due")


def test_invoice_payment_succeeded_reactivates_existing_entitlement(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    db_path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO billing_customers (user_id, provider_customer_id) VALUES (1, 'cus_123')"
        )
        conn.execute(
            """
            INSERT INTO subscriptions (
                user_id, provider_subscription_id, tier, status
            )
            VALUES (1, 'sub_123', 'personal', 'past_due')
            """
        )
    event = {
        "id": "evt_invoice_succeeded",
        "type": "invoice.payment_succeeded",
        "livemode": False,
        "data": {
            "object": {
                "id": "in_456",
                "object": "invoice",
                "customer": "cus_123",
                "subscription": "sub_123",
            }
        },
    }

    response = _post_webhook(client, event)

    assert response.status_code == 200
    with sqlite3.connect(db_path) as conn:
        entitlement = conn.execute(
            "SELECT tier, source, status FROM entitlements WHERE user_id = 1"
        ).fetchone()
        subscription = conn.execute(
            "SELECT tier, status FROM subscriptions WHERE provider_subscription_id = 'sub_123'"
        ).fetchone()

    assert entitlement == ("personal", "stripe", "active")
    assert subscription == ("personal", "active")

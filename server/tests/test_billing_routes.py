import os
import shutil
import sqlite3
import tempfile

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

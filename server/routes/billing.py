"""Billing routes for Stripe-hosted Checkout and Customer Portal sessions."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.billing_entitlements import resolve_user_entitlement
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.sql_compat import adapt_placeholders
from services.stripe_billing import (
    BillingConfigurationError,
    BillingProviderError,
    configured_checkout_tiers,
    create_checkout_session,
    create_customer_portal_session,
    create_stripe_customer,
    load_stripe_billing_config,
)


billing_bp = Blueprint("billing", __name__)


def _database_adapter() -> DatabaseAdapter:
    return current_app.config["DATABASE_ADAPTER"]


def _database_provider() -> str:
    return current_app.config.get("DATABASE_PROVIDER", SQLITE_PROVIDER)


def _sql(statement: str) -> str:
    return adapt_placeholders(statement, _database_provider())


def get_db():
    return _database_adapter().connect(timeout=10)


def _row_get(row, key: str):
    if row is None:
        return None
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, None)


def _get_billing_customer(conn, user_id: int):
    return conn.execute(
        _sql(
            """
            SELECT provider_customer_id
            FROM billing_customers
            WHERE user_id = ? AND provider = 'stripe'
            """
        ),
        (user_id,),
    ).fetchone()


def _get_profile_for_billing(conn, user_id: int):
    return conn.execute(
        _sql(
            """
            SELECT id, email, first_name, last_name, display_name, username
            FROM users
            WHERE id = ?
            """
        ),
        (user_id,),
    ).fetchone()


def _profile_name(profile) -> str:
    parts = [
        str(_row_get(profile, "first_name") or "").strip(),
        str(_row_get(profile, "last_name") or "").strip(),
    ]
    full_name = " ".join(part for part in parts if part).strip()
    return (
        full_name
        or str(_row_get(profile, "display_name") or "").strip()
        or str(_row_get(profile, "username") or "").strip()
    )


def _store_billing_customer(conn, user_id: int, provider_customer_id: str) -> None:
    conn.execute(
        _sql(
            """
            INSERT INTO billing_customers (user_id, provider, provider_customer_id)
            VALUES (?, 'stripe', ?)
            ON CONFLICT(user_id, provider) DO UPDATE SET
                provider_customer_id = excluded.provider_customer_id,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        (user_id, provider_customer_id),
    )


def _billing_status_payload(conn, user_id: int) -> dict[str, object]:
    config = load_stripe_billing_config()
    customer = _get_billing_customer(conn, user_id)
    entitlement = resolve_user_entitlement(conn, user_id)
    return {
        "entitlement": entitlement,
        "provider": "stripe",
        "stripe_configured": config.configured,
        "checkout_tiers": configured_checkout_tiers(config),
        "has_billing_customer": customer is not None,
    }


@billing_bp.route("/billing/status", methods=["GET"])
@jwt_required()
def get_billing_status():
    user_id = int(get_jwt_identity())
    with get_db() as conn:
        return jsonify(_billing_status_payload(conn, user_id)), 200


@billing_bp.route("/billing/checkout-session", methods=["POST"])
@jwt_required()
def start_checkout_session():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    tier = str(data.get("tier") or "").strip().lower()

    if not tier:
        return jsonify({"error": "Choose a billing plan."}), 400

    try:
        with get_db() as conn:
            profile = _get_profile_for_billing(conn, user_id)
            if profile is None:
                return jsonify({"error": "User not found"}), 404

            customer = _get_billing_customer(conn, user_id)
            customer_id = str(_row_get(customer, "provider_customer_id") or "").strip()
            if not customer_id:
                stripe_customer = create_stripe_customer(
                    email=str(_row_get(profile, "email") or "").strip() or None,
                    name=_profile_name(profile) or None,
                    user_id=user_id,
                )
                customer_id = str(stripe_customer.get("id") or "").strip()
                if not customer_id:
                    raise BillingProviderError("Stripe did not return a customer id.")
                _store_billing_customer(conn, user_id, customer_id)

            session = create_checkout_session(
                tier=tier,
                customer_id=customer_id,
                user_id=user_id,
            )
    except BillingConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503
    except BillingProviderError as exc:
        current_app.logger.warning("Stripe checkout session failed for user %s: %s", user_id, exc)
        return jsonify({"error": "Billing checkout could not be started."}), 502

    url = str(session.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Billing checkout did not return a redirect URL."}), 502
    return jsonify({"url": url}), 200


@billing_bp.route("/billing/customer-portal-session", methods=["POST"])
@jwt_required()
def start_customer_portal_session():
    user_id = int(get_jwt_identity())
    try:
        with get_db() as conn:
            customer = _get_billing_customer(conn, user_id)
            customer_id = str(_row_get(customer, "provider_customer_id") or "").strip()
            if not customer_id:
                return jsonify({"error": "Start a subscription before opening billing management."}), 400
            session = create_customer_portal_session(customer_id=customer_id)
    except BillingConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503
    except BillingProviderError as exc:
        current_app.logger.warning("Stripe portal session failed for user %s: %s", user_id, exc)
        return jsonify({"error": "Billing management could not be opened."}), 502

    url = str(session.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Billing management did not return a redirect URL."}), 502
    return jsonify({"url": url}), 200

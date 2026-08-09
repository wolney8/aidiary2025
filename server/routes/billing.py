"""Billing routes for Stripe-hosted Checkout and Customer Portal sessions."""

from __future__ import annotations

import json

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from services.billing_entitlements import (
    record_billing_event,
    resolve_user_entitlement,
    upsert_user_entitlement,
)
from services.database import SQLITE_PROVIDER
from services.database_adapter import DatabaseAdapter
from services.sql_compat import adapt_placeholders
from services.stripe_billing import (
    BillingConfigurationError,
    BillingProviderError,
    BillingSignatureError,
    configured_checkout_periods,
    configured_checkout_tiers,
    create_checkout_session,
    create_customer_portal_session,
    create_stripe_customer,
    load_stripe_billing_config,
    verify_stripe_webhook_event,
)
from services.plan_catalogue import list_plan_catalogue, seed_default_plan_catalogue, upsert_plan
from services.usage_limits import get_user_usage_summary


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


def _iso_from_epoch(value) -> str | None:
    if value in {None, ""}:
        return None
    try:
        from datetime import datetime, timezone

        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


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


def _get_user_id_by_customer(conn, customer_id: str) -> int | None:
    if not customer_id:
        return None
    row = conn.execute(
        _sql(
            """
            SELECT user_id
            FROM billing_customers
            WHERE provider = 'stripe' AND provider_customer_id = ?
            """
        ),
        (customer_id,),
    ).fetchone()
    user_id = _row_get(row, "user_id")
    return int(user_id) if user_id is not None else None


def _get_subscription_by_provider_id(conn, subscription_id: str):
    if not subscription_id:
        return None
    return conn.execute(
        _sql(
            """
            SELECT user_id, tier, status
            FROM subscriptions
            WHERE provider = 'stripe' AND provider_subscription_id = ?
            """
        ),
        (subscription_id,),
    ).fetchone()


def _user_exists(conn, user_id: int) -> bool:
    row = conn.execute(_sql("SELECT 1 FROM users WHERE id = ?"), (user_id,)).fetchone()
    return row is not None


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
    if not provider_customer_id:
        return
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


def _subscription_tier_from_object(subscription: dict[str, object]) -> str:
    metadata = subscription.get("metadata") if isinstance(subscription.get("metadata"), dict) else {}
    metadata_tier = str((metadata or {}).get("tier") or "").strip().lower()
    if metadata_tier in {"personal", "plus"}:
        return metadata_tier

    price_ids = load_stripe_billing_config().price_ids
    items = subscription.get("items") if isinstance(subscription.get("items"), dict) else {}
    item_rows = items.get("data") if isinstance(items.get("data"), list) else []
    for item in item_rows:
        if not isinstance(item, dict):
            continue
        price = item.get("price") if isinstance(item.get("price"), dict) else {}
        price_id = str(price.get("id") or "").strip()
        for configured_key, configured_price_id in price_ids.items():
            if configured_price_id and price_id == configured_price_id:
                tier = configured_key.split("_", 1)[0]
                if tier in {"personal", "plus"}:
                    return tier
                return tier
    return "free"


def _map_stripe_subscription_status(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"active", "trialing"}:
        return "active"
    if normalized == "past_due":
        return "past_due"
    if normalized in {"canceled", "cancelled"}:
        return "cancelled"
    if normalized == "incomplete_expired":
        return "expired"
    return "inactive"


def _upsert_subscription_from_stripe(
    conn,
    *,
    user_id: int,
    subscription: dict[str, object],
) -> dict[str, object]:
    subscription_id = str(subscription.get("id") or "").strip()
    if not subscription_id:
        raise BillingProviderError("Stripe subscription id is missing.")

    tier = _subscription_tier_from_object(subscription)
    status = _map_stripe_subscription_status(str(subscription.get("status") or ""))
    current_period_start = _iso_from_epoch(subscription.get("current_period_start"))
    current_period_end = _iso_from_epoch(subscription.get("current_period_end"))
    cancel_at_period_end = 1 if bool(subscription.get("cancel_at_period_end")) else 0
    conn.execute(
        _sql(
            """
            INSERT INTO subscriptions (
                user_id,
                provider,
                provider_subscription_id,
                tier,
                status,
                current_period_start,
                current_period_end,
                cancel_at_period_end
            )
            VALUES (?, 'stripe', ?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider, provider_subscription_id) DO UPDATE SET
                user_id = excluded.user_id,
                tier = excluded.tier,
                status = excluded.status,
                current_period_start = excluded.current_period_start,
                current_period_end = excluded.current_period_end,
                cancel_at_period_end = excluded.cancel_at_period_end,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        (
            user_id,
            subscription_id,
            tier,
            status,
            current_period_start,
            current_period_end,
            cancel_at_period_end,
        ),
    )
    entitlement = upsert_user_entitlement(
        conn,
        user_id=user_id,
        tier=tier,
        source="stripe",
        status=status,
        valid_until=current_period_end,
    )
    return {
        "subscription_id": subscription_id,
        "tier": tier,
        "status": status,
        "entitlement": entitlement,
    }


def _event_object(event: dict[str, object]) -> dict[str, object]:
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    obj = data.get("object") if isinstance(data.get("object"), dict) else {}
    return obj


def _user_id_from_metadata(value) -> int | None:
    try:
        user_id = int(str(value or "").strip())
    except (TypeError, ValueError):
        return None
    return user_id if user_id > 0 else None


def _handle_checkout_completed(conn, event: dict[str, object]) -> dict[str, object]:
    session = _event_object(event)
    metadata = session.get("metadata") if isinstance(session.get("metadata"), dict) else {}
    user_id = (
        _user_id_from_metadata(session.get("client_reference_id"))
        or _user_id_from_metadata((metadata or {}).get("openmynd_user_id"))
        or _user_id_by_customer_or_none(conn, str(session.get("customer") or "").strip())
    )
    if not user_id or not _user_exists(conn, user_id):
        raise BillingProviderError("Stripe checkout session could not be matched to a user.")

    customer_id = str(session.get("customer") or "").strip()
    _store_billing_customer(conn, user_id, customer_id)
    tier = str((metadata or {}).get("tier") or "").strip().lower()
    if tier not in {"personal", "plus"}:
        tier = "free"

    subscription_id = str(session.get("subscription") or "").strip()
    if subscription_id:
        conn.execute(
            _sql(
                """
                INSERT INTO subscriptions (
                    user_id, provider, provider_subscription_id, tier, status
                )
                VALUES (?, 'stripe', ?, ?, 'active')
                ON CONFLICT(provider, provider_subscription_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    tier = excluded.tier,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            (user_id, subscription_id, tier),
        )
    entitlement = upsert_user_entitlement(
        conn,
        user_id=user_id,
        tier=tier,
        source="stripe",
        status="active",
    )
    return {
        "user_id": user_id,
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "tier": tier,
        "status": "active",
        "entitlement": entitlement,
    }


def _user_id_by_customer_or_none(conn, customer_id: str) -> int | None:
    try:
        return _get_user_id_by_customer(conn, customer_id)
    except (TypeError, ValueError):
        return None


def _handle_subscription_event(conn, event: dict[str, object]) -> dict[str, object]:
    subscription = _event_object(event)
    customer_id = str(subscription.get("customer") or "").strip()
    user_id = _get_user_id_by_customer(conn, customer_id)
    if not user_id:
        raise BillingProviderError("Stripe subscription could not be matched to a user.")
    _store_billing_customer(conn, user_id, customer_id)
    result = _upsert_subscription_from_stripe(
        conn,
        user_id=user_id,
        subscription=subscription,
    )
    return {"user_id": user_id, "customer_id": customer_id, **result}


def _handle_invoice_event(conn, event: dict[str, object]) -> dict[str, object]:
    invoice = _event_object(event)
    customer_id = str(invoice.get("customer") or "").strip()
    subscription_id = str(invoice.get("subscription") or "").strip()
    user_id = _get_user_id_by_customer(conn, customer_id)
    if not user_id and subscription_id:
        subscription = _get_subscription_by_provider_id(conn, subscription_id)
        user_id = _row_get(subscription, "user_id")
    if not user_id:
        raise BillingProviderError("Stripe invoice could not be matched to a user.")

    subscription = _get_subscription_by_provider_id(conn, subscription_id)
    tier = str(_row_get(subscription, "tier") or "free").strip().lower()
    if tier not in {"personal", "plus"}:
        tier = "free"

    event_type = str(event.get("type") or "").strip()
    status = "past_due" if event_type == "invoice.payment_failed" else "active"
    if subscription_id:
        conn.execute(
            _sql(
                """
                INSERT INTO subscriptions (
                    user_id, provider, provider_subscription_id, tier, status
                )
                VALUES (?, 'stripe', ?, ?, ?)
                ON CONFLICT(provider, provider_subscription_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    tier = excluded.tier,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            (int(user_id), subscription_id, tier, status),
        )
    entitlement = upsert_user_entitlement(
        conn,
        user_id=int(user_id),
        tier=tier,
        source="stripe",
        status=status,
    )
    return {
        "user_id": int(user_id),
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "tier": tier,
        "status": status,
        "entitlement": entitlement,
    }


def _process_stripe_event(conn, event: dict[str, object]) -> dict[str, object]:
    event_type = str(event.get("type") or "").strip()
    if event_type == "checkout.session.completed":
        return _handle_checkout_completed(conn, event)
    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        return _handle_subscription_event(conn, event)
    if event_type in {"invoice.payment_failed", "invoice.payment_succeeded"}:
        return _handle_invoice_event(conn, event)
    return {"ignored": True, "event_type": event_type}


def _event_metadata(event: dict[str, object], result: dict[str, object] | None = None) -> dict[str, object]:
    obj = _event_object(event)
    return {
        "object_id": str(obj.get("id") or ""),
        "object_type": str(obj.get("object") or ""),
        "customer": str(obj.get("customer") or ""),
        "subscription": str(obj.get("subscription") or obj.get("id") or ""),
        "livemode": bool(event.get("livemode")),
        "result": {
            key: value
            for key, value in (result or {}).items()
            if key in {"ignored", "event_type", "user_id", "tier", "status"}
        },
    }


def _update_billing_event_metadata(
    conn,
    *,
    event_id: str,
    user_id: int | None,
    metadata: dict[str, object],
) -> None:
    conn.execute(
        _sql(
            """
            UPDATE billing_events
            SET user_id = ?, metadata_json = ?
            WHERE provider = 'stripe' AND provider_event_id = ?
            """
        ),
        (user_id, json.dumps(metadata, ensure_ascii=False), event_id),
    )


def _billing_status_payload(conn, user_id: int) -> dict[str, object]:
    config = load_stripe_billing_config()
    customer = _get_billing_customer(conn, user_id)
    entitlement = resolve_user_entitlement(conn, user_id)
    seed_default_plan_catalogue(conn)
    return {
        "entitlement": entitlement,
        "provider": "stripe",
        "stripe_configured": config.configured,
        "checkout_tiers": configured_checkout_tiers(config),
        "checkout_periods": configured_checkout_periods(config),
        "has_billing_customer": customer is not None,
        "usage": get_user_usage_summary(conn, user_id),
        "plans": list_plan_catalogue(conn, include_internal=False),
        "is_admin": entitlement.get("tier") == "administrator",
    }


def _require_admin(conn, user_id: int) -> tuple[bool, dict[str, object]]:
    entitlement = resolve_user_entitlement(conn, user_id)
    return entitlement.get("tier") == "administrator", entitlement


@billing_bp.route("/billing/status", methods=["GET"])
@jwt_required()
def get_billing_status():
    user_id = int(get_jwt_identity())
    with get_db() as conn:
        return jsonify(_billing_status_payload(conn, user_id)), 200


@billing_bp.route("/billing/plans", methods=["GET"])
@jwt_required()
def get_billing_plans():
    user_id = int(get_jwt_identity())
    with get_db() as conn:
        try:
            entitlement = resolve_user_entitlement(conn, user_id)
        except Exception as exc:
            current_app.logger.warning(
                "Plan catalogue request using default entitlement for user %s: %s",
                user_id,
                exc,
            )
            entitlement = {"tier": "free"}
        seed_default_plan_catalogue(conn)
        config = load_stripe_billing_config()
        include_internal = entitlement.get("tier") == "administrator" and (
            request.args.get("include_internal") == "1"
        )
        return jsonify(
            {
                "plans": list_plan_catalogue(conn, include_internal=include_internal),
                "is_admin": entitlement.get("tier") == "administrator",
                "stripe_configured": config.configured,
                "checkout_tiers": configured_checkout_tiers(config),
                "checkout_periods": configured_checkout_periods(config),
            }
        ), 200


@billing_bp.route("/billing/admin/plans", methods=["GET"])
@jwt_required()
def get_admin_billing_plans():
    user_id = int(get_jwt_identity())
    with get_db() as conn:
        is_admin, _entitlement = _require_admin(conn, user_id)
        if not is_admin:
            return jsonify({"error": "Administrator access is required."}), 403
        seed_default_plan_catalogue(conn)
        return jsonify({"plans": list_plan_catalogue(conn, include_internal=True)}), 200


@billing_bp.route("/billing/admin/plans/<tier>", methods=["PUT"])
@jwt_required()
def update_admin_billing_plan(tier: str):
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    payload["tier"] = tier
    try:
        with get_db() as conn:
            is_admin, _entitlement = _require_admin(conn, user_id)
            if not is_admin:
                return jsonify({"error": "Administrator access is required."}), 403
            plan = upsert_plan(conn, payload)
            return jsonify({"plan": plan}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@billing_bp.route("/billing/checkout-session", methods=["POST"])
@jwt_required()
def start_checkout_session():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    tier = str(data.get("tier") or "").strip().lower()
    billing_period = str(data.get("billing_period") or "monthly").strip().lower()

    if not tier:
        return jsonify({"error": "Choose a billing plan."}), 400
    if billing_period not in {"monthly", "annual"}:
        return jsonify({"error": "Choose monthly or annual billing."}), 400

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
                billing_period=billing_period,
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


@billing_bp.route("/billing/stripe/webhook", methods=["POST"])
def receive_stripe_webhook():
    config = load_stripe_billing_config()
    payload = request.get_data(cache=False)
    signature_header = request.headers.get("Stripe-Signature", "")
    try:
        event = verify_stripe_webhook_event(
            payload=payload,
            signature_header=signature_header,
            webhook_secret=config.webhook_secret,
        )
    except BillingConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503
    except BillingSignatureError:
        return jsonify({"error": "Invalid Stripe webhook signature."}), 400

    event_id = str(event.get("id") or "").strip()
    event_type = str(event.get("type") or "").strip()
    if not event_id or not event_type:
        return jsonify({"error": "Invalid Stripe event payload."}), 400

    try:
        with get_db() as conn:
            inserted = record_billing_event(
                conn,
                provider="stripe",
                provider_event_id=event_id,
                event_type=event_type,
                metadata=_event_metadata(event),
            )
            if not inserted:
                return jsonify({"received": True, "duplicate": True}), 200

            result = _process_stripe_event(conn, event)
            _update_billing_event_metadata(
                conn,
                user_id=result.get("user_id") if isinstance(result.get("user_id"), int) else None,
                event_id=event_id,
                metadata=_event_metadata(event, result),
            )
    except BillingProviderError as exc:
        current_app.logger.warning("Stripe webhook processing failed for %s: %s", event_type, exc)
        return jsonify({"error": "Stripe webhook could not be processed."}), 422
    except ValueError as exc:
        current_app.logger.warning("Stripe webhook event rejected for %s: %s", event_type, exc)
        return jsonify({"error": "Stripe webhook event was invalid."}), 400

    return jsonify({"received": True, "duplicate": False}), 200


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

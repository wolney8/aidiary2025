"""Stripe Checkout, Customer Portal, and webhook verification helpers."""

from __future__ import annotations

import os
import json
import hmac
import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx


STRIPE_API_BASE = "https://api.stripe.com/v1"
REQUEST_TIMEOUT_SECONDS = 20
CHECKOUT_TIERS = ("personal", "plus")
WEBHOOK_TOLERANCE_SECONDS = 300


class BillingConfigurationError(RuntimeError):
    """Raised when Stripe billing is not configured for the current environment."""


class BillingProviderError(RuntimeError):
    """Raised when Stripe rejects or fails a session request."""


class BillingSignatureError(ValueError):
    """Raised when a Stripe webhook signature cannot be verified."""


@dataclass(frozen=True)
class StripeBillingConfig:
    secret_key: str
    webhook_secret: str
    price_ids: dict[str, str]
    success_url: str
    cancel_url: str
    portal_return_url: str

    @property
    def configured(self) -> bool:
        return bool(self.secret_key and any(self.price_ids.values()))


def load_stripe_billing_config() -> StripeBillingConfig:
    frontend_base = (os.getenv("FRONTEND_BASE_URL") or "http://localhost:4200").rstrip("/")
    legacy_personal_price = os.getenv("STRIPE_PRICE_PERSONAL", "").strip()
    legacy_plus_price = os.getenv("STRIPE_PRICE_PLUS", "").strip()
    price_ids = {
        "personal": legacy_personal_price,
        "plus": legacy_plus_price,
        "personal_monthly": os.getenv("STRIPE_PRICE_PERSONAL_MONTHLY", "").strip()
        or legacy_personal_price,
        "personal_annual": os.getenv("STRIPE_PRICE_PERSONAL_ANNUAL", "").strip(),
        "plus_monthly": os.getenv("STRIPE_PRICE_PLUS_MONTHLY", "").strip()
        or legacy_plus_price,
        "plus_annual": os.getenv("STRIPE_PRICE_PLUS_ANNUAL", "").strip(),
    }
    return StripeBillingConfig(
        secret_key=os.getenv("STRIPE_SECRET_KEY", "").strip(),
        webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", "").strip(),
        price_ids=price_ids,
        success_url=(
            os.getenv("STRIPE_CHECKOUT_SUCCESS_URL", "").strip()
            or urljoin(f"{frontend_base}/", "account?billing=success")
        ),
        cancel_url=(
            os.getenv("STRIPE_CHECKOUT_CANCEL_URL", "").strip()
            or urljoin(f"{frontend_base}/", "account?billing=cancelled")
        ),
        portal_return_url=(
            os.getenv("STRIPE_CUSTOMER_PORTAL_RETURN_URL", "").strip()
            or urljoin(f"{frontend_base}/", "account")
        ),
    )


def verify_stripe_webhook_event(
    *,
    payload: bytes,
    signature_header: str,
    webhook_secret: str,
    tolerance_seconds: int = WEBHOOK_TOLERANCE_SECONDS,
    now: int | None = None,
) -> dict[str, Any]:
    """Verify a Stripe webhook signature and return the decoded event payload."""
    if not webhook_secret:
        raise BillingConfigurationError("Stripe webhook signing secret is not configured.")
    if not payload:
        raise BillingSignatureError("Webhook payload is empty.")

    timestamp, signatures = _parse_signature_header(signature_header)
    current_time = int(now if now is not None else time.time())
    if abs(current_time - timestamp) > tolerance_seconds:
        raise BillingSignatureError("Webhook signature timestamp is outside tolerance.")

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    if not any(hmac.compare_digest(expected_signature, signature) for signature in signatures):
        raise BillingSignatureError("Webhook signature verification failed.")

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BillingSignatureError("Webhook payload is not valid JSON.") from exc
    if not isinstance(decoded, dict):
        raise BillingSignatureError("Webhook payload must be an object.")
    return decoded


def _parse_signature_header(signature_header: str) -> tuple[int, list[str]]:
    if not signature_header:
        raise BillingSignatureError("Stripe-Signature header is missing.")

    values: dict[str, list[str]] = {}
    for item in signature_header.split(","):
        key, separator, value = item.partition("=")
        if not separator:
            continue
        values.setdefault(key.strip(), []).append(value.strip())

    try:
        timestamp = int(values.get("t", [""])[0])
    except ValueError as exc:
        raise BillingSignatureError("Stripe-Signature timestamp is invalid.") from exc
    signatures = [signature for signature in values.get("v1", []) if signature]
    if not signatures:
        raise BillingSignatureError("Stripe-Signature header has no v1 signatures.")
    return timestamp, signatures


def configured_checkout_tiers(config: StripeBillingConfig | None = None) -> list[str]:
    active_config = config or load_stripe_billing_config()
    return [
        tier
        for tier in CHECKOUT_TIERS
        if (
            active_config.price_ids.get(tier)
            or active_config.price_ids.get(f"{tier}_monthly")
            or active_config.price_ids.get(f"{tier}_annual")
        )
    ]


def configured_checkout_periods(config: StripeBillingConfig | None = None) -> dict[str, list[str]]:
    active_config = config or load_stripe_billing_config()
    periods: dict[str, list[str]] = {}
    for tier in CHECKOUT_TIERS:
        configured_periods: list[str] = []
        if active_config.price_ids.get(f"{tier}_monthly") or active_config.price_ids.get(tier):
            configured_periods.append("monthly")
        if active_config.price_ids.get(f"{tier}_annual"):
            configured_periods.append("annual")
        if configured_periods:
            periods[tier] = configured_periods
    return periods


def create_stripe_customer(
    *,
    email: str | None,
    name: str | None,
    user_id: int,
    config: StripeBillingConfig | None = None,
) -> dict[str, Any]:
    active_config = _require_secret_key(config)
    payload: dict[str, Any] = {
        "metadata[openmynd_user_id]": str(user_id),
    }
    if email:
        payload["email"] = email
    if name:
        payload["name"] = name
    return _stripe_post("/customers", payload, active_config)


def create_checkout_session(
    *,
    tier: str,
    billing_period: str = "monthly",
    customer_id: str,
    user_id: int,
    config: StripeBillingConfig | None = None,
) -> dict[str, Any]:
    active_config = _require_secret_key(config)
    normalized_tier = (tier or "").strip().lower()
    normalized_period = (billing_period or "monthly").strip().lower()
    if normalized_period not in {"monthly", "annual"}:
        raise BillingConfigurationError("Choose monthly or annual billing.")
    if normalized_period == "annual":
        price_id = active_config.price_ids.get(f"{normalized_tier}_annual")
    else:
        price_id = (
            active_config.price_ids.get(f"{normalized_tier}_monthly")
            or active_config.price_ids.get(normalized_tier)
        )
    if normalized_tier not in CHECKOUT_TIERS or not price_id:
        raise BillingConfigurationError("This billing plan is not configured.")

    return _stripe_post(
        "/checkout/sessions",
        {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": str(user_id),
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": active_config.success_url,
            "cancel_url": active_config.cancel_url,
            "metadata[openmynd_user_id]": str(user_id),
            "metadata[tier]": normalized_tier,
            "metadata[billing_period]": normalized_period,
        },
        active_config,
    )


def create_customer_portal_session(
    *,
    customer_id: str,
    config: StripeBillingConfig | None = None,
) -> dict[str, Any]:
    active_config = _require_secret_key(config)
    if not customer_id:
        raise BillingConfigurationError("A Stripe customer is required for the billing portal.")
    return _stripe_post(
        "/billing_portal/sessions",
        {
            "customer": customer_id,
            "return_url": active_config.portal_return_url,
        },
        active_config,
    )


def _require_secret_key(config: StripeBillingConfig | None = None) -> StripeBillingConfig:
    active_config = config or load_stripe_billing_config()
    if not active_config.secret_key:
        raise BillingConfigurationError("Stripe billing is not configured.")
    return active_config


def _stripe_post(
    path: str,
    payload: dict[str, Any],
    config: StripeBillingConfig,
) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{STRIPE_API_BASE}{path}",
            data=payload,
            auth=(config.secret_key, ""),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise BillingProviderError("Stripe rejected the billing request.") from exc
    except httpx.HTTPError as exc:
        raise BillingProviderError("Stripe could not be reached.") from exc

    data = response.json()
    if not isinstance(data, dict):
        raise BillingProviderError("Stripe returned an invalid response.")
    return data

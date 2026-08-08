"""Stripe Checkout and Customer Portal integration.

This module deliberately only creates Stripe-hosted sessions. Webhook processing remains
the source of truth for paid entitlement synchronisation in the follow-on billing issue.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx


STRIPE_API_BASE = "https://api.stripe.com/v1"
REQUEST_TIMEOUT_SECONDS = 20
CHECKOUT_TIERS = ("personal", "plus")


class BillingConfigurationError(RuntimeError):
    """Raised when Stripe billing is not configured for the current environment."""


class BillingProviderError(RuntimeError):
    """Raised when Stripe rejects or fails a session request."""


@dataclass(frozen=True)
class StripeBillingConfig:
    secret_key: str
    price_ids: dict[str, str]
    success_url: str
    cancel_url: str
    portal_return_url: str

    @property
    def configured(self) -> bool:
        return bool(self.secret_key and any(self.price_ids.values()))


def load_stripe_billing_config() -> StripeBillingConfig:
    frontend_base = (os.getenv("FRONTEND_BASE_URL") or "http://localhost:4200").rstrip("/")
    price_ids = {
        "personal": os.getenv("STRIPE_PRICE_PERSONAL", "").strip(),
        "plus": os.getenv("STRIPE_PRICE_PLUS", "").strip(),
    }
    return StripeBillingConfig(
        secret_key=os.getenv("STRIPE_SECRET_KEY", "").strip(),
        price_ids=price_ids,
        success_url=(
            os.getenv("STRIPE_CHECKOUT_SUCCESS_URL", "").strip()
            or urljoin(f"{frontend_base}/", "profile?billing=success")
        ),
        cancel_url=(
            os.getenv("STRIPE_CHECKOUT_CANCEL_URL", "").strip()
            or urljoin(f"{frontend_base}/", "profile?billing=cancelled")
        ),
        portal_return_url=(
            os.getenv("STRIPE_CUSTOMER_PORTAL_RETURN_URL", "").strip()
            or urljoin(f"{frontend_base}/", "profile")
        ),
    )


def configured_checkout_tiers(config: StripeBillingConfig | None = None) -> list[str]:
    active_config = config or load_stripe_billing_config()
    return [tier for tier in CHECKOUT_TIERS if active_config.price_ids.get(tier)]


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
    customer_id: str,
    user_id: int,
    config: StripeBillingConfig | None = None,
) -> dict[str, Any]:
    active_config = _require_secret_key(config)
    normalized_tier = (tier or "").strip().lower()
    price_id = active_config.price_ids.get(normalized_tier)
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

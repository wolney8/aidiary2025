from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

import httpx

from services.database import SQLITE_PROVIDER
from services.sql_compat import adapt_placeholders

AVAILABLE_COUNTRIES_URL = "https://date.nager.at/api/v3/AvailableCountries"
PUBLIC_HOLIDAYS_URL_TEMPLATE = "https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
REQUEST_TIMEOUT_SECONDS = 10.0

FALLBACK_COUNTRIES: tuple[dict[str, str], ...] = (
    {"countryCode": "AU", "name": "Australia"},
    {"countryCode": "CA", "name": "Canada"},
    {"countryCode": "FR", "name": "France"},
    {"countryCode": "DE", "name": "Germany"},
    {"countryCode": "IE", "name": "Ireland"},
    {"countryCode": "NZ", "name": "New Zealand"},
    {"countryCode": "GB", "name": "United Kingdom"},
    {"countryCode": "US", "name": "United States"},
)


def _serialise_holiday(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": item.get("date", ""),
        "localName": item.get("localName", ""),
        "name": item.get("name", ""),
        "countryCode": item.get("countryCode", ""),
        "fixed": bool(item.get("fixed", False)),
        "global": bool(item.get("global", False)),
        "counties": item.get("counties"),
        "launchYear": item.get("launchYear"),
        "types": item.get("types") or [],
    }


def list_available_countries() -> list[dict[str, str]]:
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(AVAILABLE_COUNTRIES_URL)
        response.raise_for_status()
        payload = response.json()

    countries: list[dict[str, str]] = []
    for item in payload:
        country_code = str(item.get("countryCode", "")).strip().upper()
        name = str(item.get("name", "")).strip()
        if not country_code or not name:
            continue
        countries.append({"countryCode": country_code, "name": name})

    countries.sort(key=lambda item: item["name"])
    return countries


def list_fallback_countries() -> list[dict[str, str]]:
    """Small stable fallback so Customisation remains usable if the provider is unavailable."""
    return sorted(
        (dict(country) for country in FALLBACK_COUNTRIES),
        key=lambda item: item["name"],
    )


def _row_value(row: object, key: str, index: int) -> object:
    if isinstance(row, Mapping):
        return row[key]
    return row[index]


def get_public_holidays(
    conn,
    *,
    country_code: str,
    year: int,
    provider: str = SQLITE_PROVIDER,
) -> list[dict[str, Any]]:
    normalised_country_code = country_code.strip().upper()
    cached_row = conn.execute(
        adapt_placeholders(
            """
        SELECT payload_json
        FROM public_holiday_cache
        WHERE country_code = ? AND holiday_year = ?
        """,
            provider,
        ),
        (normalised_country_code, year),
    ).fetchone()
    if cached_row:
        return json.loads(str(_row_value(cached_row, "payload_json", 0)))

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(
            PUBLIC_HOLIDAYS_URL_TEMPLATE.format(
                year=year,
                country_code=normalised_country_code,
            )
        )
        response.raise_for_status()
        payload = response.json()

    serialised_payload = [_serialise_holiday(item) for item in payload]
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        adapt_placeholders(
            """
        INSERT INTO public_holiday_cache (
            country_code, holiday_year, payload_json, fetched_at
        ) VALUES (?, ?, ?, ?)
        ON CONFLICT(country_code, holiday_year)
        DO UPDATE SET payload_json = excluded.payload_json, fetched_at = excluded.fetched_at
        """,
            provider,
        ),
        (
            normalised_country_code,
            year,
            json.dumps(serialised_payload),
            fetched_at,
        ),
    )
    return serialised_payload

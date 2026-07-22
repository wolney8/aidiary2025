import json
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest
import httpx

from app import create_app


@pytest.fixture
def client_with_legacy_user_schema():
    db_fd, db_path = tempfile.mkstemp()
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET"] = "test-secret"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            age INTEGER,
            sex TEXT,
            goals TEXT,
            dailydiary_api_key TEXT,
            dreamdiary_api_key TEXT,
            chatgpt_daily_diary_coachname TEXT,
            chatgpt_dream_diary_coachname TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client, db_path

    os.close(db_fd)
    os.unlink(db_path)


def _register_and_get_token(client) -> str:
    response = client.post(
        "/api/register",
        data=json.dumps({"username": "holiday-user", "password": "testpass123"}),
        content_type="application/json",
    )
    return json.loads(response.data)["token"]


@patch("routes.public_holidays.list_available_countries")
def test_public_holiday_countries_endpoint_returns_provider_data(
    mock_list_available_countries,
    client_with_legacy_user_schema,
):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    mock_list_available_countries.return_value = [
        {"countryCode": "GB", "name": "United Kingdom"},
        {"countryCode": "US", "name": "United States"},
    ]

    response = client.get(
        "/api/public-holidays/countries",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert json.loads(response.data)[0]["countryCode"] == "GB"


@patch("routes.public_holidays.list_available_countries")
def test_public_holiday_countries_endpoint_uses_fallback_when_provider_fails(
    mock_list_available_countries,
    client_with_legacy_user_schema,
):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    mock_list_available_countries.side_effect = httpx.ConnectError(
        "provider unavailable"
    )

    response = client.get(
        "/api/public-holidays/countries",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert {"countryCode": "GB", "name": "United Kingdom"} in payload
    assert {"countryCode": "US", "name": "United States"} in payload


@patch("services.public_holidays.httpx.Client")
def test_public_holidays_endpoint_fetches_and_caches_holidays(
    mock_httpx_client,
    client_with_legacy_user_schema,
):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {"holiday_country_code": "GB", "show_public_holidays": True}
        ),
        content_type="application/json",
    )

    mock_client = MagicMock()
    mock_httpx_client.return_value.__enter__.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "date": "2026-12-25",
            "localName": "Christmas Day",
            "name": "Christmas Day",
            "countryCode": "GB",
            "fixed": True,
            "global": True,
            "counties": None,
            "launchYear": None,
            "types": ["Public"],
        }
    ]
    mock_response.raise_for_status.return_value = None
    mock_client.get.return_value = mock_response

    response = client.get(
        "/api/public-holidays?year=2026",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["year"] == 2026
    assert payload["countryCode"] == "GB"
    assert payload["enabled"] is True
    assert payload["holidays"][0]["name"] == "Christmas Day"

    conn = sqlite3.connect(db_path)
    cached_rows = conn.execute(
        "SELECT country_code, holiday_year FROM public_holiday_cache"
    ).fetchall()
    conn.close()
    assert cached_rows == [("GB", 2026)]

    mock_client.get.reset_mock()
    second_response = client.get(
        "/api/public-holidays?year=2026",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second_response.status_code == 200
    mock_client.get.assert_not_called()


def test_public_holidays_endpoint_returns_empty_when_disabled(
    client_with_legacy_user_schema,
):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.get(
        "/api/public-holidays?year=2026",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["year"] == 2026
    assert payload["enabled"] is False
    assert payload["holidays"] == []

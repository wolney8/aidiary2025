import json
import os
import sqlite3
import tempfile

import pytest

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
        data=json.dumps({"username": "profile-user", "password": "testpass123"}),
        content_type="application/json",
    )
    return json.loads(response.data)["token"]


def test_runtime_migration_adds_user_settings_columns(client_with_legacy_user_schema):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.get(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["timezone"] == "UTC"
    assert data["ai_tone"] == "friendly"
    assert data["ai_verbosity"] == "balanced"
    assert data["ai_focus"] == "reflective"
    assert data["allow_ai_history"] == 1

    conn = sqlite3.connect(db_path)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    conn.close()

    assert "display_name" in columns
    assert "pronouns" in columns
    assert "timezone" in columns
    assert "ai_tone" in columns
    assert "ai_verbosity" in columns
    assert "ai_focus" in columns
    assert "allow_ai_history" in columns


def test_profile_update_accepts_personalisation_fields(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "display_name": "Alex",
                "pronouns": "they/them",
                "timezone": "Europe/London",
                "ai_tone": "empathetic",
                "ai_verbosity": "detailed",
                "ai_focus": "creative-prompts",
                "allow_ai_history": False,
                "chatgpt_daily_diary_coachname": "Sage",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Profile updated"
    assert data["user"]["display_name"] == "Alex"
    assert data["user"]["pronouns"] == "they/them"
    assert data["user"]["timezone"] == "Europe/London"
    assert data["user"]["ai_tone"] == "empathetic"
    assert data["user"]["ai_verbosity"] == "detailed"
    assert data["user"]["ai_focus"] == "creative-prompts"
    assert data["user"]["allow_ai_history"] == 0
    assert data["user"]["chatgpt_daily_diary_coachname"] == "Sage"


def test_profile_update_rejects_invalid_ai_tone(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"ai_tone": "playful"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"] == "Invalid AI tone"


def test_profile_update_trims_display_name_and_timezone(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "display_name": "  Alex  ",
                "timezone": "  Europe/London  ",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["user"]["display_name"] == "Alex"
    assert data["user"]["timezone"] == "Europe/London"


def test_profile_update_rejects_overlong_pronouns(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"pronouns": "x" * 41}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"] == "Maximum length is 40 characters"

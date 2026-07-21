import json
import os
import sqlite3
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app import create_app


@pytest.fixture
def client_with_legacy_user_schema():
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["MEDIA_ROOT"] = media_root

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
    for path in sorted(Path(media_root).rglob('*'), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    Path(media_root).rmdir()


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
    assert data["ai_model"] == "gpt-4.1-mini"
    assert data["allow_ai_history"] == 1
    assert data["allow_ai_attachment_context"] == 0
    assert data["holiday_country_code"] is None
    assert data["show_public_holidays"] == 0

    conn = sqlite3.connect(db_path)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    conn.close()

    assert "display_name" in columns
    assert "pronouns" in columns
    assert "gender" in columns
    assert "custom_guidance" in columns
    assert "timezone" in columns
    assert "ai_tone" in columns
    assert "ai_verbosity" in columns
    assert "ai_focus" in columns
    assert "ai_model" in columns
    assert "allow_ai_history" in columns
    assert "allow_ai_attachment_context" in columns
    assert "holiday_country_code" in columns
    assert "show_public_holidays" in columns
    assert "profile_picture_storage_key" in columns


def test_profile_picture_upload_normalises_replaces_and_deletes(
    client_with_legacy_user_schema,
):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    source = BytesIO()
    Image.new("RGB", (900, 500), (30, 120, 210)).save(source, format="PNG")
    response = client.post(
        "/api/profile/picture",
        headers=headers,
        data={"image": (BytesIO(source.getvalue()), "portrait.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["user"]["profile_picture_url"].endswith(".jpg")

    with sqlite3.connect(db_path) as conn:
        storage_key = conn.execute(
            "SELECT profile_picture_storage_key FROM users WHERE id = 1"
        ).fetchone()[0]
    image_path = Path(os.environ["MEDIA_ROOT"]) / storage_key
    assert image_path.exists()
    with Image.open(image_path) as stored_image:
        assert stored_image.size == (400, 400)
        assert stored_image.format == "JPEG"

    replacement = BytesIO()
    Image.new("RGB", (300, 700), (180, 40, 80)).save(replacement, format="WEBP")
    replace_response = client.post(
        "/api/profile/picture",
        headers=headers,
        data={"image": (BytesIO(replacement.getvalue()), "replacement.webp")},
        content_type="multipart/form-data",
    )
    assert replace_response.status_code == 200
    assert not image_path.exists()

    delete_response = client.delete("/api/profile/picture", headers=headers)
    assert delete_response.status_code == 200
    assert json.loads(delete_response.data)["user"]["profile_picture_url"] is None

    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT profile_picture_storage_key FROM users WHERE id = 1"
        ).fetchone()[0] is None


def test_profile_picture_upload_rejects_invalid_content(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.post(
        "/api/profile/picture",
        headers={"Authorization": f"Bearer {token}"},
        data={"image": (BytesIO(b"not an image"), "fake.jpg")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == "Choose a valid JPEG, PNG, or WebP image"


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
                "gender": "non-binary",
                "custom_guidance": "Help me stay grounded",
                "timezone": "Europe/London",
                "holiday_country_code": "gb",
                "show_public_holidays": True,
                "ai_tone": "empathetic",
                "ai_verbosity": "detailed",
                "ai_focus": "creative-prompts",
                "ai_model": "gpt-4.1",
                "allow_ai_history": False,
                "allow_ai_attachment_context": False,
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
    assert data["user"]["gender"] == "non-binary"
    assert data["user"]["custom_guidance"] == "Help me stay grounded"
    assert data["user"]["timezone"] == "Europe/London"
    assert data["user"]["holiday_country_code"] == "GB"
    assert data["user"]["show_public_holidays"] == 1
    assert data["user"]["ai_tone"] == "empathetic"
    assert data["user"]["ai_verbosity"] == "detailed"
    assert data["user"]["ai_focus"] == "creative-prompts"
    assert data["user"]["ai_model"] == "gpt-4.1"
    assert data["user"]["allow_ai_history"] == 0
    assert data["user"]["allow_ai_attachment_context"] == 0
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


def test_profile_update_rejects_invalid_holiday_country_code(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"holiday_country_code": "United Kingdom"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"] == "Holiday country must use a two-letter country code"


def test_profile_update_rejects_invalid_ai_model(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"ai_model": "gpt-3.5-turbo"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"] == "Invalid AI model"


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


def test_profile_update_rejects_invalid_timezone(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"timezone": "London-ish"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == "Timezone must be a valid IANA timezone"


def test_profile_update_rejects_invalid_pronouns_choice(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"pronouns": "xe/xem"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"] == "Invalid pronouns"


def test_profile_update_rejects_invalid_gender_choice(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"gender": "female"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data["error"] == "Invalid gender"


def test_profile_update_rejects_invalid_display_name(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"display_name": "Alex123"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert (
        data["error"]
        == "Display name may only use letters, spaces, apostrophes, and hyphens"
    )


def test_profile_update_rejects_invalid_custom_guidance(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"custom_guidance": "Use <script>alert(1)</script>"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert (
        data["error"]
        == "Custom guidance may only use plain text, numbers, spaces, and basic punctuation"
    )

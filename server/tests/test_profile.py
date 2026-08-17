import json
import os
import sqlite3
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from flask import Flask
from PIL import Image

from app import create_app
from routes import profile


class _FakePostgresRows:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _FakePostgresConnection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return _FakePostgresRows([
            {
                "id": 1,
                "username": "profile-user",
                "email": "oauth@example.com",
                "auth_provider": "google",
                "registered_at": "2026-08-06T09:00:00Z",
                "first_name": None,
                "last_name": None,
                "age": None,
                "date_of_birth": None,
                "sex": None,
                "goals": None,
                "dailydiary_api_key": None,
                "dreamdiary_api_key": None,
                "chatgpt_daily_diary_coachname": None,
                "chatgpt_dream_diary_coachname": None,
                "display_name": "Will",
                "pronouns": "he/him",
                "gender": "man",
                "custom_guidance": None,
                "timezone": "Europe/London",
                "holiday_country_code": "GB",
                "show_public_holidays": 1,
                "show_on_this_day": 1,
                "ai_tone": "friendly",
                "ai_verbosity": "balanced",
                "ai_focus": "reflective",
                "ai_model": "gpt-4.1-mini",
                "allow_ai_history": 1,
                "allow_ai_attachment_context": 0,
                "writing_reminders_enabled": 0,
                "writing_reminder_days": None,
                "writing_reminder_time": "19:00",
                "writing_reminder_silence_days": 3,
                "writing_reminder_entry_types": "daily,dream",
                "writing_rhythm_progress_enabled": 0,
                "writing_rhythm_weekly_goal": 4,
                "chat_enabled": 1,
                "password_auth_enabled": 1,
                "onboarding_completed": 1,
                "profile_picture_storage_key": None,
            }
        ])


class _FakePostgresAdapter:
    def table_exists(self, _conn, table_name):
        assert table_name == "auth_identities"
        return True

    def table_columns(self, _conn, table_name):
        assert table_name == "users"
        return {"id", "account_status"}


@pytest.fixture
def client_with_legacy_user_schema():
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp()
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["MEDIA_ROOT"] = media_root
    os.environ["AUTH_LOGIN_RATE_LIMIT"] = "1000 per minute"
    os.environ["AUTH_REGISTER_RATE_LIMIT"] = "1000 per minute"
    os.environ["ACCOUNT_DELETE_RATE_LIMIT"] = "1000 per minute"

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


def test_profile_helpers_use_postgres_placeholders():
    app = Flask(__name__)
    app.config["DATABASE_PROVIDER"] = "postgres"
    app.config["DATABASE_ADAPTER"] = _FakePostgresAdapter()
    conn = _FakePostgresConnection()

    with app.app_context():
        user = profile._select_profile(conn, 1)
        update_sql = profile._sql(
            """
            UPDATE users
            SET display_name = ?, timezone = ?
            WHERE id = ?
            """
        )

    select_sql, select_params = conn.calls[0]
    assert "FROM users WHERE users.id = %s" in select_sql
    assert select_params == (1,)
    assert user["display_name"] == "Will"
    assert user["email"] == "oauth@example.com"
    assert "display_name = %s" in update_sql
    assert "timezone = %s" in update_sql
    assert "WHERE id = %s" in update_sql


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
    assert data["show_on_this_day"] == 0
    assert data["writing_reminders_enabled"] == 0
    assert data["writing_reminder_days"] is None
    assert data["writing_reminder_time"] == "19:00"
    assert data["writing_reminder_silence_days"] == 3
    assert data["writing_reminder_entry_types"] == "daily,dream"
    assert data["writing_rhythm_progress_enabled"] == 0
    assert data["writing_rhythm_weekly_goal"] == 4
    assert data["chat_enabled"] == 1
    assert data["password_auth_enabled"] == 1
    assert data["onboarding_completed"] == 1
    assert data["email"] is None
    assert data["auth_provider"] is None

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
    assert "show_on_this_day" in columns
    assert "profile_picture_storage_key" in columns
    assert "writing_reminders_enabled" in columns
    assert "writing_reminder_days" in columns
    assert "writing_reminder_time" in columns
    assert "writing_reminder_silence_days" in columns
    assert "writing_reminder_entry_types" in columns
    assert "writing_rhythm_progress_enabled" in columns
    assert "writing_rhythm_weekly_goal" in columns
    assert "chat_enabled" in columns
    assert "password_auth_enabled" in columns
    assert "onboarding_completed" in columns


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


def test_profile_media_asset_cleanup_lists_and_deletes_owned_attachments(
    client_with_legacy_user_schema,
):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    media_root = Path(os.environ["MEDIA_ROOT"])
    storage_key = "entries/daily-assets/1/cleanup.pdf"
    media_path = media_root / storage_key
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"pdf-bytes")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date TEXT,
                title TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_date TEXT,
                title TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO dailydiary_entries (id, user_id, entry_date, title)
            VALUES (10, 1, '2026-08-17', 'Stored attachment entry')
            """
        )
        conn.execute(
            """
            INSERT INTO entry_assets (
                id, user_id, entry_type, entry_id, asset_role, storage_key,
                original_filename, mime_type, file_size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                99,
                1,
                "daily",
                10,
                "attachment",
                storage_key,
                "cleanup.pdf",
                "application/pdf",
                len(b"pdf-bytes"),
            ),
        )

    list_response = client.get("/api/profile/media-assets", headers=headers)
    assert list_response.status_code == 200
    assets = json.loads(list_response.data)["assets"]
    assert assets == [
        {
            "id": 99,
            "entry_type": "daily",
            "entry_id": 10,
            "entry_title": "Stored attachment entry",
            "entry_date": "2026-08-17",
            "filename": "cleanup.pdf",
            "mime_type": "application/pdf",
            "file_size_bytes": len(b"pdf-bytes"),
            "url": "http://localhost/media/entries/daily-assets/1/cleanup.pdf",
        }
    ]

    delete_response = client.delete("/api/profile/media-assets/99", headers=headers)
    assert delete_response.status_code == 200
    assert json.loads(delete_response.data)["deleted_asset_id"] == 99
    assert not media_path.exists()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM entry_assets").fetchone()[0] == 0


def test_profile_media_asset_cleanup_rejects_other_user_asset(
    client_with_legacy_user_schema,
):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO entry_assets (
                id, user_id, entry_type, entry_id, asset_role, storage_key,
                original_filename, mime_type, file_size_bytes
            )
            VALUES (
                5, 2, 'daily', 1, 'attachment', 'entries/daily-assets/2/private.pdf',
                'private.pdf', 'application/pdf', 10
            )
            """
        )

    response = client.delete(
        "/api/profile/media-assets/5",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert json.loads(response.data)["error"] == "Media asset not found"


def test_account_delete_requires_confirmation_and_removes_user_data(
    client_with_legacy_user_schema,
):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    media_root = Path(os.environ["MEDIA_ROOT"])
    storage_key = "entries/daily/1/delete-me.jpg"
    media_path = media_root / storage_key
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"image-bytes")

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE users SET profile_picture_storage_key = ? WHERE id = 1",
            (storage_key,)
        )

    blocked_response = client.delete(
        "/api/profile/account",
        headers=headers,
        data=json.dumps({
            "password": "testpass123",
            "confirmation": "DELETE",
        }),
        content_type="application/json",
    )
    assert blocked_response.status_code == 400

    wrong_password_response = client.delete(
        "/api/profile/account",
        headers=headers,
        data=json.dumps({
            "password": "wrongpass123",
            "confirmation": "DELETE MY ACCOUNT",
        }),
        content_type="application/json",
    )
    assert wrong_password_response.status_code == 400
    assert json.loads(wrong_password_response.data)["error"] == "Password did not match."
    assert media_path.exists()
    with sqlite3.connect(db_path) as conn:
        failed_event = conn.execute(
            """
            SELECT event_type, outcome, user_id, metadata_json
            FROM security_audit_events
            WHERE event_type = 'account_delete_failed'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    assert failed_event[0:3] == ("account_delete_failed", "rejected", 1)
    assert json.loads(failed_event[3]) == {"reason": "bad_password"}

    delete_response = client.delete(
        "/api/profile/account",
        headers=headers,
        data=json.dumps({
            "password": "testpass123",
            "confirmation": "DELETE MY ACCOUNT",
        }),
        content_type="application/json",
    )

    assert delete_response.status_code == 200
    assert json.loads(delete_response.data)["message"] == "Account deleted"
    assert not media_path.exists()

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        events = conn.execute(
            """
            SELECT event_type, outcome, user_id, metadata_json
            FROM security_audit_events
            ORDER BY id
            """
        ).fetchall()
    assert events == [
        (
            "account_delete_success",
            "success",
            None,
            '{"user_rows_removed": true}',
        )
    ]


def test_oauth_only_account_deletion_does_not_require_password(client_with_legacy_user_schema):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE users SET password_auth_enabled = 0 WHERE id = 1")
        conn.execute(
            """
            INSERT INTO auth_identities (
                user_id, provider, provider_subject, email, email_verified
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (1, "google", "deleted-google-user", "deleted@example.com", 1),
        )

    delete_response = client.delete(
        "/api/profile/account",
        headers=headers,
        data=json.dumps({
            "password": "",
            "confirmation": "DELETE MY ACCOUNT",
        }),
        content_type="application/json",
    )

    assert delete_response.status_code == 200
    assert json.loads(delete_response.data)["message"] == "Account deleted"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM auth_identities").fetchone()[0] == 0


def test_account_delete_rate_limit_is_enforced(client_with_legacy_user_schema, monkeypatch):
    monkeypatch.setenv("ACCOUNT_DELETE_RATE_LIMIT", "1 per minute")
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "password": "wrongpass123",
        "confirmation": "DELETE MY ACCOUNT",
    }

    first = client.delete(
        "/api/profile/account",
        headers=headers,
        data=json.dumps(payload),
        content_type="application/json",
    )
    second = client.delete(
        "/api/profile/account",
        headers=headers,
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert first.status_code == 400
    assert second.status_code == 429
    assert json.loads(second.data)["error"] == "Too many attempts. Try again shortly."


def test_profile_update_accepts_personalisation_fields(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "display_name": "Alex",
                "date_of_birth": "1990-05-12",
                "pronouns": "they/them",
                "gender": "non-binary",
                "custom_guidance": "Help me stay grounded",
                "timezone": "Europe/London",
                "holiday_country_code": "gb",
                "show_public_holidays": True,
                "show_on_this_day": True,
                "ai_tone": "empathetic",
                "ai_verbosity": "detailed",
                "ai_focus": "creative-prompts",
                "ai_model": "gpt-4.1",
                "allow_ai_history": False,
                "allow_ai_attachment_context": False,
                "writing_reminders_enabled": True,
                "writing_reminder_days": ["monday", "wednesday", "friday"],
                "writing_reminder_time": "18:30",
                "writing_reminder_silence_days": 5,
                "writing_reminder_entry_types": ["daily", "dream", "thought_record"],
                "writing_rhythm_progress_enabled": True,
                "writing_rhythm_weekly_goal": 6,
                "chat_enabled": False,
                "chatgpt_daily_diary_coachname": "Sage",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["message"] == "Profile updated"
    assert data["user"]["display_name"] == "Alex"
    assert data["user"]["date_of_birth"] == "1990-05-12"
    assert data["user"]["pronouns"] == "they/them"
    assert data["user"]["gender"] == "non-binary"
    assert data["user"]["custom_guidance"] == "Help me stay grounded"
    assert data["user"]["timezone"] == "Europe/London"
    assert data["user"]["holiday_country_code"] == "GB"
    assert data["user"]["show_public_holidays"] == 1
    assert data["user"]["show_on_this_day"] == 1
    assert data["user"]["ai_tone"] == "empathetic"
    assert data["user"]["ai_verbosity"] == "detailed"
    assert data["user"]["ai_focus"] == "creative-prompts"
    assert data["user"]["ai_model"] == "gpt-4.1"
    assert data["user"]["allow_ai_history"] == 0
    assert data["user"]["allow_ai_attachment_context"] == 0
    assert data["user"]["writing_reminders_enabled"] == 1
    assert data["user"]["writing_reminder_days"] == "monday,wednesday,friday"
    assert data["user"]["writing_reminder_time"] == "18:30"
    assert data["user"]["writing_reminder_silence_days"] == 5
    assert data["user"]["writing_reminder_entry_types"] == (
        "daily,dream,thought_record"
    )
    assert data["user"]["writing_rhythm_progress_enabled"] == 1
    assert data["user"]["writing_rhythm_weekly_goal"] == 6
    assert data["user"]["chat_enabled"] == 0
    assert data["user"]["chatgpt_daily_diary_coachname"] == "Sage"


def test_profile_update_rejects_invalid_writing_reminder_values(
    client_with_legacy_user_schema,
):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"writing_reminder_days": ["monday", "funday"]}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == "Reminder days must be valid weekdays"

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"writing_reminder_time": "7pm"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == "Reminder time must use HH:MM format"

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"writing_reminder_silence_days": 60}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == (
        "Reminder silence days must be between 1 and 30"
    )

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"writing_reminder_entry_types": ["daily", "gratitude"]}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == (
        "Reminder entry types must be valid record types"
    )

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"writing_rhythm_weekly_goal": 30}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == (
        "Weekly writing goal must be between 1 and 21"
    )


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


def test_profile_update_rejects_invalid_date_of_birth_format(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"date_of_birth": "12/05/1990"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == (
        "Date of birth must use YYYY-MM-DD format"
    )


def test_profile_update_rejects_future_date_of_birth(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client)

    response = client.put(
        "/api/profile",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps({"date_of_birth": "2999-01-01"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.data)["error"] == "Date of birth cannot be in the future"


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
        data=json.dumps({"display_name": "Alex 123"}),
        content_type="application/json",
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert (
        data["error"]
        == "Display name may only use letters, numbers, hyphens, and underscores"
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
        == "Custom guidance must be plain text only; code or script-like text is not allowed"
    )

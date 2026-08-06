import json
import os
import shutil
import sqlite3
import tempfile
from io import BytesIO

import pytest
from flask import Flask
from PIL import Image

from app import create_app
from routes import important_days


@pytest.fixture
def client_with_legacy_user_schema():
    db_fd, db_path = tempfile.mkstemp()
    media_root = tempfile.mkdtemp(prefix="aidiary-important-days-media-")
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
    shutil.rmtree(media_root, ignore_errors=True)


def _tiny_image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (320, 180), (40, 120, 200)).save(output, format="PNG")
    output.seek(0)
    return output.read()


def _register_and_get_token(client, username: str) -> str:
    response = client.post(
        "/api/register",
        data=json.dumps({"username": username, "password": "testpass123"}),
        content_type="application/json",
    )
    return json.loads(response.data)["token"]


def test_important_day_sql_helpers_support_postgres_placeholders_and_returning_id():
    app = Flask(__name__)
    app.config["DATABASE_PROVIDER"] = "postgres"

    with app.app_context():
        list_sql = important_days._sql(
            f"""
            {important_days.IMPORTANT_DAY_SELECT}
            WHERE user_id = ?
            ORDER BY month ASC
            """
        )
        insert_sql = important_days._sql(
            important_days.append_returning_id(
                """
                INSERT INTO important_days (
                    user_id, label, starts_on, month, day, original_year,
                    category, recurrence, icon_name, accent_color, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                important_days._database_provider(),
            )
        )

    assert "WHERE user_id = %s" in list_sql
    assert "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)" in insert_sql
    assert "RETURNING id" in insert_sql


def test_runtime_migration_creates_important_days_table(client_with_legacy_user_schema):
    _client, db_path = client_with_legacy_user_schema

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    conn.close()

    assert "important_days" in tables


def test_create_and_list_important_days_are_user_scoped(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token_one = _register_and_get_token(client, "important-days-a")
    token_two = _register_and_get_token(client, "important-days-b")

    create_response = client.post(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token_one}"},
        data=json.dumps(
            {
                "label": "Katie birthday",
                "starts_on": "2021-08-05",
                "original_year": 2021,
                "category": "birthday",
                "recurrence": "yearly",
                "icon_name": "cake",
                "accent_color": "amber",
                "note": "Keep it low-key",
            }
        ),
        content_type="application/json",
    )

    assert create_response.status_code == 201
    created_day = json.loads(create_response.data)
    assert created_day["label"] == "Katie birthday"
    assert created_day["category"] == "birthday"
    assert created_day["starts_on"] == "2021-08-05"
    assert created_day["month"] == 8
    assert created_day["day"] == 5
    assert created_day["recurrence"] == "yearly"
    assert created_day["icon_name"] == "cake"
    assert created_day["accent_color"] == "amber"

    first_user_days = client.get(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token_one}"},
    )
    assert first_user_days.status_code == 200
    first_user_payload = json.loads(first_user_days.data)
    assert len(first_user_payload) == 1
    assert first_user_payload[0]["label"] == "Katie birthday"

    second_user_days = client.get(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token_two}"},
    )
    assert second_user_days.status_code == 200
    assert json.loads(second_user_days.data) == []


def test_update_and_delete_important_day(client_with_legacy_user_schema):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client, "important-days-edit")

    create_response = client.post(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "label": "Anniversary",
                "starts_on": "2024-02-14",
                "category": "anniversary",
                "recurrence": "yearly",
                "icon_name": "favorite",
                "accent_color": "rose",
            }
        ),
        content_type="application/json",
    )
    important_day_id = json.loads(create_response.data)["id"]

    update_response = client.put(
        f"/api/important-days/{important_day_id}",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "label": "Engagement anniversary",
                "starts_on": "2024-02-14",
                "original_year": 2024,
                "category": "milestone",
                "recurrence": "once",
                "icon_name": "flag",
                "accent_color": "blue",
                "note": "Book dinner",
            }
        ),
        content_type="application/json",
    )

    assert update_response.status_code == 200
    updated_day = json.loads(update_response.data)
    assert updated_day["label"] == "Engagement anniversary"
    assert updated_day["category"] == "milestone"
    assert updated_day["recurrence"] == "once"
    assert updated_day["icon_name"] == "flag"
    assert updated_day["accent_color"] == "blue"
    assert updated_day["note"] == "Book dinner"

    delete_response = client.delete(
        f"/api/important-days/{important_day_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 200
    assert json.loads(delete_response.data)["message"] == "Important day deleted"

    list_response = client.get(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert json.loads(list_response.data) == []


def test_upload_and_delete_important_day_image(client_with_legacy_user_schema):
    client, db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client, "important-days-image")

    create_response = client.post(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "label": "Photo day",
                "starts_on": "2025-07-20",
                "category": "milestone",
            }
        ),
        content_type="application/json",
    )
    important_day_id = json.loads(create_response.data)["id"]

    upload_response = client.post(
        f"/api/important-days/{important_day_id}/image",
        headers={"Authorization": f"Bearer {token}"},
        data={"image": (BytesIO(_tiny_image_bytes()), "photo.png")},
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 200
    upload_payload = json.loads(upload_response.data)
    assert upload_payload["has_image"] is True
    assert upload_payload["image_url"].startswith("http://localhost/media/")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT image_storage_key, image_url FROM important_days WHERE id = ?",
        (important_day_id,),
    ).fetchone()
    conn.close()
    assert row["image_storage_key"]
    assert row["image_url"] is None
    stored_image_path = os.path.join(
        os.environ["MEDIA_ROOT"], *row["image_storage_key"].split("/")
    )
    assert os.path.exists(stored_image_path)

    list_response = client.get(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
    )
    listed_day = json.loads(list_response.data)[0]
    assert listed_day["has_image"] is True
    assert listed_day["image_url"].startswith("http://localhost/media/")

    delete_response = client.delete(
        f"/api/important-days/{important_day_id}/image",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 200
    delete_payload = json.loads(delete_response.data)
    assert delete_payload["has_image"] is False
    assert delete_payload["image_url"] is None
    assert not os.path.exists(stored_image_path)

    conn = sqlite3.connect(db_path)
    cleared_row = conn.execute(
        "SELECT image_storage_key, image_url FROM important_days WHERE id = ?",
        (important_day_id,),
    ).fetchone()
    conn.close()
    assert cleared_row == (None, None)


def test_create_important_day_rejects_invalid_date_and_category(
    client_with_legacy_user_schema,
):
    client, _db_path = client_with_legacy_user_schema
    token = _register_and_get_token(client, "important-days-invalid")

    invalid_date = client.post(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "label": "Impossible date",
                "starts_on": "2024-02-31",
                "category": "other",
            }
        ),
        content_type="application/json",
    )
    assert invalid_date.status_code == 400
    assert json.loads(invalid_date.data)["error"] == "Date must use YYYY-MM-DD"

    invalid_category = client.post(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "label": "Unknown category",
                "starts_on": "2024-06-19",
                "category": "holiday",
            }
        ),
        content_type="application/json",
    )
    assert invalid_category.status_code == 400
    assert json.loads(invalid_category.data)["error"] == "Category is invalid"

    invalid_recurrence = client.post(
        "/api/important-days",
        headers={"Authorization": f"Bearer {token}"},
        data=json.dumps(
            {
                "label": "Invalid recurrence",
                "starts_on": "2024-06-19",
                "category": "other",
                "recurrence": "weekly",
            }
        ),
        content_type="application/json",
    )
    assert invalid_recurrence.status_code == 400
    assert json.loads(invalid_recurrence.data)["error"] == "Recurrence is invalid"

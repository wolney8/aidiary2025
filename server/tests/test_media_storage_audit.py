import sqlite3

from scripts.audit_media_storage import audit_media_storage
from services.database_adapter import DatabaseAdapter


def _create_media_audit_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                profile_picture_storage_key TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE dailydiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                image_storage_key TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE dreamdiary_entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                image_storage_key TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE important_days (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                image_storage_key TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE entry_assets (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                entry_type TEXT,
                entry_id INTEGER,
                storage_key TEXT,
                original_filename TEXT
            )
            """
        )

        conn.execute(
            "INSERT INTO users (id, profile_picture_storage_key) VALUES (1, ?)",
            ("profiles/1/avatar.jpg",),
        )
        conn.execute(
            "INSERT INTO dailydiary_entries (id, user_id, image_storage_key) VALUES (10, 1, ?)",
            ("entries/daily/1/present.jpg",),
        )
        conn.execute(
            "INSERT INTO dreamdiary_entries (id, user_id, image_storage_key) VALUES (11, 1, ?)",
            ("entries/dream/1/missing.png",),
        )
        conn.execute(
            "INSERT INTO important_days (id, user_id, image_storage_key) VALUES (12, 1, ?)",
            ("../bad.jpg",),
        )
        conn.execute(
            """
            INSERT INTO entry_assets (
                id, user_id, entry_type, entry_id, storage_key, original_filename
            ) VALUES (20, 1, 'daily', 10, ?, 'note.pdf')
            """,
            ("entries/daily-assets/1/note.pdf",),
        )


def test_audit_media_storage_reports_missing_and_invalid_references(tmp_path):
    db_path = tmp_path / "app.db"
    media_root = tmp_path / "media"
    (media_root / "profiles/1").mkdir(parents=True)
    (media_root / "profiles/1/avatar.jpg").write_bytes(b"avatar")
    (media_root / "entries/daily/1").mkdir(parents=True)
    (media_root / "entries/daily/1/present.jpg").write_bytes(b"image")
    _create_media_audit_db(db_path)

    report = audit_media_storage(
        adapter=DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path)),
        media_root=media_root,
    )

    assert report["ready_for_cutover"] is False
    assert report["summary"] == {
        "references_checked": 5,
        "present": 2,
        "missing": 2,
        "invalid": 1,
        "missing_details_returned": 2,
        "invalid_details_returned": 1,
    }
    assert {item["source"] for item in report["missing"]} == {
        "dream_images",
        "entry_assets",
    }
    assert report["invalid"] == [
        {
            "source": "important_day_images",
            "table": "important_days",
            "record_id": 12,
            "user_id": 1,
            "storage_key": "../bad.jpg",
            "reason": "Invalid media storage key.",
        }
    ]


def test_audit_media_storage_passes_when_references_exist(tmp_path):
    db_path = tmp_path / "app.db"
    media_root = tmp_path / "media"
    for storage_key in [
        "profiles/1/avatar.jpg",
        "entries/daily/1/present.jpg",
        "entries/dream/1/missing.png",
        "entries/daily-assets/1/note.pdf",
    ]:
        path = media_root / storage_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ok")
    _create_media_audit_db(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE important_days SET image_storage_key = ? WHERE id = 12",
            ("entries/important-day/1/photo.jpg",),
        )
    path = media_root / "entries/important-day/1/photo.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ok")

    report = audit_media_storage(
        adapter=DatabaseAdapter(provider="sqlite", sqlite_path=str(db_path)),
        media_root=media_root,
    )

    assert report["ready_for_cutover"] is True
    assert report["summary"]["references_checked"] == 5
    assert report["summary"]["missing"] == 0
    assert report["summary"]["invalid"] == 0

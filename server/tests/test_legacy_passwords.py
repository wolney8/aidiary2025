import sqlite3

import bcrypt

from services.legacy_passwords import (
    bcrypt_password,
    migrate_legacy_passwords,
    password_is_bcrypt_hash,
)


def _create_users_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT
        )
        """
    )


def test_password_is_bcrypt_hash_accepts_standard_bcrypt_prefixes():
    assert password_is_bcrypt_hash("$2a$12$abcdefghijklmnopqrstuu123456789012345678901234567")
    assert password_is_bcrypt_hash("$2b$12$abcdefghijklmnopqrstuu123456789012345678901234567")
    assert password_is_bcrypt_hash("$2y$12$abcdefghijklmnopqrstuu123456789012345678901234567")
    assert not password_is_bcrypt_hash("plaintext-password")
    assert not password_is_bcrypt_hash("")


def test_legacy_password_migration_dry_run_does_not_write(tmp_path):
    db_path = tmp_path / "legacy-passwords.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _create_users_table(conn)
        conn.execute(
            "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
            (1, "legacy", "legacy-pass-123"),
        )
        conn.execute(
            "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
            (2, "modern", bcrypt_password("password123")),
        )

        report = migrate_legacy_passwords(conn, apply=False)
        stored_password = conn.execute(
            "SELECT password FROM users WHERE id = 1"
        ).fetchone()["password"]

    assert report.ok is True
    assert report.total_users_scanned == 2
    assert report.legacy_passwords_found == 1
    assert report.migrated == 0
    assert report.migrated_user_ids == ()
    assert stored_password == "legacy-pass-123"


def test_legacy_password_migration_apply_hashes_plaintext_rows(tmp_path):
    db_path = tmp_path / "legacy-passwords.db"
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        _create_users_table(conn)
        conn.execute(
            "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
            (1, "legacy", "legacy-pass-123"),
        )
        conn.execute(
            "INSERT INTO users (id, username, password) VALUES (?, ?, ?)",
            (2, "empty", ""),
        )

        report = migrate_legacy_passwords(conn, apply=True)
        rows = conn.execute(
            "SELECT id, password FROM users ORDER BY id"
        ).fetchall()

    assert report.ok is True
    assert report.legacy_passwords_found == 2
    assert report.migrated == 1
    assert report.skipped_empty_passwords == 1
    assert report.migrated_user_ids == (1,)
    assert rows[0]["password"].startswith("$2b$")
    assert bcrypt.checkpw("legacy-pass-123".encode("utf-8"), rows[0]["password"].encode("utf-8"))
    assert rows[1]["password"] == ""

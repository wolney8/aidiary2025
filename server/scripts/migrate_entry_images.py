"""Migrate legacy DB-inline entry images into media storage.

Usage:
    cd server
    source venv/bin/activate
    PYTHONPATH=. python scripts/migrate_entry_images.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sqlite3

from app import create_app
from routes.entries import get_db
from services.media_storage import is_legacy_data_url, migrate_legacy_data_url


def migrate_legacy_entry_images(*, dry_run: bool) -> int:
    app = create_app()
    migrated = 0

    with app.app_context():
        conn = get_db()
        try:
            for table_name, entry_kind in (
                ("dailydiary_entries", "daily"),
                ("dreamdiary_entries", "dream"),
            ):
                rows = conn.execute(
                    f"""
                    SELECT id, user_id, image_url, image_storage_key
                    FROM {table_name}
                    WHERE image_storage_key IS NULL
                      AND image_url IS NOT NULL
                    """
                ).fetchall()

                for row in rows:
                    legacy_value = row["image_url"]
                    if not is_legacy_data_url(legacy_value):
                        continue

                    migrated += 1
                    if dry_run:
                        continue

                    storage_key = migrate_legacy_data_url(
                        legacy_value,
                        user_id=int(row["user_id"]),
                        entry_kind=entry_kind,
                    )
                    conn.execute(
                        f"""
                        UPDATE {table_name}
                        SET image_storage_key = ?, image_url = NULL
                        WHERE id = ? AND user_id = ?
                        """,
                        (storage_key, row["id"], row["user_id"]),
                    )

            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        finally:
            conn.close()

    return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many legacy images would be migrated without changing the database.",
    )
    args = parser.parse_args()

    migrated = migrate_legacy_entry_images(dry_run=args.dry_run)
    mode = "would be migrated" if args.dry_run else "migrated"
    print(f"{migrated} legacy entry images {mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

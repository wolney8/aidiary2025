#!/usr/bin/env python3
"""Create chat_messages table and index if they do not already exist."""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


def resolve_db_path(db_path_arg: str | None) -> Path:
    """Resolve DB path from CLI arg, env var, or repository default."""
    if db_path_arg:
        return Path(db_path_arg)

    env_db_path = os.getenv("DB_PATH")
    if env_db_path:
        return Path(env_db_path)

    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "server" / "db" / "app.db"


def run_migration(db_path: Path) -> None:
    """Apply idempotent migration for chat_messages table and index."""
    print(f"Applying chat_messages migration on: {db_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                token_count INTEGER DEFAULT 0
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_user_conv
            ON chat_messages(user_id, conversation_id, created_at)
            """
        )

        connection.commit()

    print("Migration completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add chat_messages table and index to the SQLite database."
    )
    parser.add_argument(
        "--db-path",
        dest="db_path",
        help="Explicit SQLite DB path. Defaults to DB_PATH env var or server/db/app.db.",
    )
    args = parser.parse_args()

    run_migration(resolve_db_path(args.db_path))


if __name__ == "__main__":
    main()
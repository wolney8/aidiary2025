"""Database provider configuration helpers.

This module is the first runtime boundary for the SQLite-to-Postgres migration.
SQLite remains the only active app provider until route SQL has been adapted.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SUPPORTED_DATABASE_PROVIDERS = {"sqlite", "postgres"}
SQLITE_PROVIDER = "sqlite"
POSTGRES_PROVIDER = "postgres"


@dataclass(frozen=True)
class DatabaseSettings:
    provider: str
    sqlite_path: str
    database_url: str | None
    runtime_migrations_enabled: bool


def _resolve_sqlite_path(root_path: str, env_db_path: str | None) -> str:
    fallback_path = Path(root_path) / "db" / "app.db"
    if env_db_path:
        candidate = Path(env_db_path)
        resolved_path = candidate if candidate.is_absolute() else Path(root_path) / candidate
        if resolved_path.exists():
            return str(resolved_path)
        if fallback_path.exists():
            return str(fallback_path)
        return str(resolved_path)
    return str(fallback_path)


def resolve_database_settings(
    root_path: str,
    environ: Mapping[str, str] | None = None,
) -> DatabaseSettings:
    env = os.environ if environ is None else environ
    provider = (env.get("DATABASE_PROVIDER") or SQLITE_PROVIDER).strip().lower()
    if provider not in SUPPORTED_DATABASE_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_DATABASE_PROVIDERS))
        raise RuntimeError(f"Unsupported DATABASE_PROVIDER '{provider}'. Use one of: {supported}")

    sqlite_path = _resolve_sqlite_path(root_path, env.get("DB_PATH"))
    database_url = (env.get("DATABASE_URL") or "").strip() or None

    if provider == "postgres" and not database_url:
        raise RuntimeError("DATABASE_URL must be configured when DATABASE_PROVIDER=postgres")

    return DatabaseSettings(
        provider=provider,
        sqlite_path=sqlite_path,
        database_url=database_url,
        runtime_migrations_enabled=provider == SQLITE_PROVIDER,
    )


def configure_app_database(app) -> DatabaseSettings:
    settings = resolve_database_settings(app.root_path)
    if settings.provider == POSTGRES_PROVIDER:
        raise RuntimeError(
            "DATABASE_PROVIDER=postgres is recognised but the runtime SQL adapter is not "
            "implemented yet. Use the migration rehearsal tools for Postgres loads until "
            "the provider adapter lands."
        )

    app.config["DATABASE_PROVIDER"] = settings.provider
    app.config["DATABASE_PATH"] = settings.sqlite_path
    app.config["DATABASE_URL"] = settings.database_url
    app.config["DATABASE_RUNTIME_MIGRATIONS_ENABLED"] = settings.runtime_migrations_enabled
    return settings


def connect_sqlite(
    app,
    *,
    log_label: str = "Database",
    timeout: int = 30,
    foreign_keys: bool = False,
    journal_mode_wal: bool = False,
) -> sqlite3.Connection:
    if app.config.get("DATABASE_PROVIDER", SQLITE_PROVIDER) != SQLITE_PROVIDER:
        raise RuntimeError("SQLite connection requested while DATABASE_PROVIDER is not sqlite")
    db_path = app.config["DATABASE_PATH"]
    app.logger.debug("%s get_db connecting to %s", log_label, db_path)
    return connect_sqlite_path(
        db_path,
        timeout=timeout,
        foreign_keys=foreign_keys,
        journal_mode_wal=journal_mode_wal,
    )


def connect_sqlite_path(
    database_path: str,
    *,
    timeout: int = 30,
    foreign_keys: bool = False,
    journal_mode_wal: bool = False,
) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON")
    if journal_mode_wal:
        conn.execute("PRAGMA journal_mode=WAL")
    return conn


def table_info(conn: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    try:
        return list(conn.execute(f"PRAGMA table_info({table_name})"))
    except sqlite3.OperationalError:
        return []


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in table_info(conn, table_name)}

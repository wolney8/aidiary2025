"""Provider-neutral database connection adapter.

Routes still migrate incrementally, but this module is the shared runtime seam for
SQLite now and Postgres later.
"""

from __future__ import annotations

import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from services.database import (
    POSTGRES_PROVIDER,
    SQLITE_PROVIDER,
    DatabaseSettings,
    connect_sqlite_path,
)
from services.sql_compat import adapt_placeholders


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REQUIRED_RUNTIME_SCHEMA: dict[str, set[str]] = {
    "users": {
        "id",
        "username",
        "password",
        "email",
        "email_verified",
        "chat_enabled",
        "password_auth_enabled",
        "onboarding_completed",
        "account_status",
        "registered_at",
    },
    "auth_identities": {"id", "user_id", "provider", "provider_subject"},
    "auth_sessions": {"id", "user_id", "jwt_jti"},
    "billing_customers": {"user_id", "stripe_customer_id"},
    "subscriptions": {"user_id", "tier", "status"},
    "entitlements": {"user_id", "tier", "status"},
    "billing_plans": {"tier", "public_name", "quotas_json"},
    "admin_announcements": {"id", "title", "message", "status"},
    "dailydiary_entries": {"id", "user_id", "entry_date", "user_message"},
    "dreamdiary_entries": {"id", "user_id", "entry_date", "plot"},
    "important_days": {"id", "user_id", "label", "starts_on"},
    "cbt_worksheets": {"id", "user_id", "worksheet_type", "record_date"},
    "cbt_thought_record_data": {"worksheet_id"},
    "entry_assets": {"id", "user_id", "entry_type", "storage_key"},
}


class _SqlCompatCursor:
    def __init__(self, cursor, provider: str):
        self._cursor = cursor
        self._provider = provider
        self.database_provider = provider
        self.connection = self

    def execute(self, sql: str, params=None):
        self._cursor.execute(adapt_placeholders(sql, self._provider), params or ())
        return self

    def executemany(self, sql: str, params_seq):
        self._cursor.executemany(adapt_placeholders(sql, self._provider), params_seq)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)


class _SqlCompatConnection:
    def __init__(self, conn, provider: str):
        self._conn = conn
        self._provider = provider
        self.database_provider = provider

    def execute(self, sql: str, params=None):
        return self._conn.execute(adapt_placeholders(sql, self._provider), params or ())

    def executemany(self, sql: str, params_seq):
        return self._conn.executemany(adapt_placeholders(sql, self._provider), params_seq)

    def cursor(self):
        return _SqlCompatCursor(self._conn.cursor(), self._provider)

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def _validate_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier}")
    return identifier


@dataclass(frozen=True)
class DatabaseAdapter:
    provider: str
    sqlite_path: str
    database_url: str | None = None

    @classmethod
    def from_settings(cls, settings: DatabaseSettings) -> "DatabaseAdapter":
        return cls(
            provider=settings.provider,
            sqlite_path=settings.sqlite_path,
            database_url=settings.database_url,
        )

    @classmethod
    def from_app(cls, app) -> "DatabaseAdapter":
        return cls(
            provider=app.config.get("DATABASE_PROVIDER", SQLITE_PROVIDER),
            sqlite_path=app.config["DATABASE_PATH"],
            database_url=app.config.get("DATABASE_URL"),
        )

    @contextmanager
    def connect(
        self,
        *,
        timeout: int = 30,
        foreign_keys: bool = False,
        journal_mode_wal: bool = False,
    ) -> Iterator[object]:
        conn = self.open(
            timeout=timeout,
            foreign_keys=foreign_keys,
            journal_mode_wal=journal_mode_wal,
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def open(
        self,
        *,
        timeout: int = 30,
        foreign_keys: bool = False,
        journal_mode_wal: bool = False,
    ) -> object:
        if self.provider == SQLITE_PROVIDER:
            return connect_sqlite_path(
                self.sqlite_path,
                timeout=timeout,
                foreign_keys=foreign_keys,
                journal_mode_wal=journal_mode_wal,
            )

        if self.provider == POSTGRES_PROVIDER:
            if not self.database_url:
                raise RuntimeError("DATABASE_URL is required for Postgres connections")
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError(
                    'psycopg is required for Postgres runtime connections. '
                    'Install with: pip install "psycopg[binary]"'
                ) from exc

            conn = psycopg.connect(
                self.database_url,
                connect_timeout=timeout,
                row_factory=dict_row,
            )
            return _SqlCompatConnection(conn, self.provider)

        raise ValueError(f"Unsupported database provider: {self.provider}")

    def health_check(self, *, write: bool = False) -> dict[str, object]:
        started_at = time.perf_counter()
        report: dict[str, object] = {
            "provider": self.provider,
            "ok": False,
            "read_ok": False,
            "write_ok": None if not write else False,
            "latency_ms": None,
        }
        try:
            with self.connect(timeout=5) as conn:
                conn.execute("SELECT 1").fetchone()
                report["read_ok"] = True
                if write:
                    conn.execute(
                        """
                        CREATE TEMP TABLE IF NOT EXISTS openmynd_database_health_probe (
                            id TEXT PRIMARY KEY,
                            checked_at TEXT NOT NULL
                        )
                        """
                    )
                    conn.execute(
                        """
                        INSERT INTO openmynd_database_health_probe (id, checked_at)
                        VALUES (?, ?)
                        """,
                        (str(uuid.uuid4()), str(time.time())),
                    )
                    report["write_ok"] = True
        except Exception as exc:
            # Keep public health output free of DSNs, credentials, hosts, and row data.
            report["error_type"] = exc.__class__.__name__
            report["message"] = "Database connection check failed."
            return report

        report["ok"] = True
        report["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
        return report

    def schema_readiness(self) -> dict[str, object]:
        """Check critical runtime tables/columns without exposing row data."""
        started_at = time.perf_counter()
        report: dict[str, object] = {
            "ok": False,
            "missing_tables": [],
            "missing_columns": {},
            "checked_tables": sorted(REQUIRED_RUNTIME_SCHEMA),
            "latency_ms": None,
        }
        try:
            with self.connect(timeout=5) as conn:
                missing_tables: list[str] = []
                missing_columns: dict[str, list[str]] = {}
                for table_name, required_columns in REQUIRED_RUNTIME_SCHEMA.items():
                    if not self.table_exists(conn, table_name):
                        missing_tables.append(table_name)
                        continue
                    existing_columns = self.table_columns(conn, table_name)
                    missing = sorted(required_columns - existing_columns)
                    if missing:
                        missing_columns[table_name] = missing

                report["missing_tables"] = sorted(missing_tables)
                report["missing_columns"] = missing_columns
                report["ok"] = not missing_tables and not missing_columns
                report["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
        except Exception as exc:
            report["error_type"] = exc.__class__.__name__
            report["message"] = "Database schema readiness check failed."

        return report

    def table_exists(self, conn, table_name: str) -> bool:
        table_name = _validate_identifier(table_name)
        if self.provider == SQLITE_PROVIDER:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            return row is not None

        if self.provider == POSTGRES_PROVIDER:
            row = conn.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = ?
                """,
                (table_name,),
            ).fetchone()
            return row is not None

        raise ValueError(f"Unsupported database provider: {self.provider}")

    def table_columns(self, conn, table_name: str) -> set[str]:
        table_name = _validate_identifier(table_name)
        if self.provider == SQLITE_PROVIDER:
            return {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }

        if self.provider == POSTGRES_PROVIDER:
            rows = conn.execute(
                adapt_placeholders(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = ?
                    """,
                    self.provider,
                ),
                (table_name,),
            ).fetchall()
            return {str(row["column_name"]) for row in rows}

        raise ValueError(f"Unsupported database provider: {self.provider}")


def get_database_adapter(app) -> DatabaseAdapter:
    return DatabaseAdapter.from_app(app)

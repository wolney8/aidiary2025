"""Provider-neutral database connection adapter.

Routes still migrate incrementally, but this module is the shared runtime seam for
SQLite now and Postgres later.
"""

from __future__ import annotations

import re
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
        if self.provider == SQLITE_PROVIDER:
            conn = connect_sqlite_path(
                self.sqlite_path,
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
            return

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

            with psycopg.connect(
                self.database_url,
                connect_timeout=timeout,
                row_factory=dict_row,
            ) as conn:
                yield conn
            return

        raise ValueError(f"Unsupported database provider: {self.provider}")

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
                  AND table_name = $1
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

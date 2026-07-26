"""Provider-neutral database connection adapter.

Routes still migrate incrementally, but this module is the shared runtime seam for
SQLite now and Postgres later.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from services.database import (
    POSTGRES_PROVIDER,
    SQLITE_PROVIDER,
    DatabaseSettings,
    connect_sqlite_path,
)


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


def get_database_adapter(app) -> DatabaseAdapter:
    return DatabaseAdapter.from_app(app)

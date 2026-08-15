"""Database failure classification for user-safe API responses."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseFailure:
    code: str
    category: str
    status_code: int
    user_message: str


READ_METHODS = {"GET", "HEAD", "OPTIONS"}


_CONNECTION_MARKERS = (
    "connection",
    "connect",
    "could not translate host",
    "could not connect",
    "connection refused",
    "connection timed out",
    "connection closed",
    "server closed the connection",
    "terminating connection",
    "network",
    "timeout",
    "temporarily unavailable",
)

_STORAGE_MARKERS = (
    "quota",
    "storage",
    "disk",
    "no space",
    "database or disk is full",
    "out of memory",
    "insufficient resources",
    "too many connections",
    "max connections",
)

_WRITE_LOCK_MARKERS = (
    "database is locked",
    "database table is locked",
    "read-only",
    "readonly",
    "cannot execute",
    "failed to commit",
    "transaction",
)


def classify_database_exception(
    exc: BaseException,
    *,
    operation: str = "write",
) -> DatabaseFailure | None:
    """Return a sanitized failure classification for database infrastructure errors."""

    if not _looks_like_database_exception(exc):
        return None

    is_read = operation == "read"
    text = f"{exc.__class__.__module__} {exc.__class__.__name__} {exc}".lower()
    if any(marker in text for marker in _STORAGE_MARKERS):
        return DatabaseFailure(
            code="database_storage_exhausted",
            category="storage_or_quota",
            status_code=507,
            user_message=(
                "OpenMynd could not save because the database storage or quota limit "
                "was reached. Your changes were not saved."
            ),
        )
    if any(marker in text for marker in _WRITE_LOCK_MARKERS):
        return DatabaseFailure(
            code="database_write_unavailable",
            category="write_unavailable",
            status_code=503,
            user_message=(
                "OpenMynd could not save because the database is temporarily not "
                "accepting writes. Your changes were not saved."
            ),
        )
    if any(marker in text for marker in _CONNECTION_MARKERS):
        return DatabaseFailure(
            code="database_unavailable",
            category="connection",
            status_code=503,
            user_message=(
                "OpenMynd could not reach the database. Try again in a moment."
                if is_read
                else "OpenMynd could not reach the database. Your changes were not saved."
            ),
        )
    return DatabaseFailure(
        code="database_read_failed" if is_read else "database_write_failed",
        category="database",
        status_code=503,
        user_message=(
            "OpenMynd could not read from the database. Try again in a moment."
            if is_read
            else "OpenMynd could not complete the database write. Your changes were not saved."
        ),
    )


def _looks_like_database_exception(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.DatabaseError):
        return True
    module_name = exc.__class__.__module__.lower()
    class_name = exc.__class__.__name__.lower()
    return "psycopg" in module_name or "sqlalchemy" in module_name or "database" in class_name

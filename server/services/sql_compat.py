"""Small SQL compatibility helpers for the SQLite-to-Postgres migration."""

from __future__ import annotations

from typing import Iterable, Sequence


SQLITE_PROVIDER = "sqlite"
POSTGRES_PROVIDER = "postgres"


def placeholder(index: int, provider: str) -> str:
    if provider == SQLITE_PROVIDER:
        return "?"
    if provider == POSTGRES_PROVIDER:
        if index < 1:
            raise ValueError("Postgres placeholders are 1-based")
        return f"${index}"
    raise ValueError(f"Unsupported database provider: {provider}")


def placeholders(count: int, provider: str, *, start: int = 1) -> str:
    if count < 0:
        raise ValueError("Placeholder count cannot be negative")
    return ", ".join(placeholder(start + offset, provider) for offset in range(count))


def in_placeholders(values: Sequence[object], provider: str, *, start: int = 1) -> str:
    if not values:
        raise ValueError("IN placeholder values cannot be empty")
    return placeholders(len(values), provider, start=start)


def adapt_placeholders(sql: str, provider: str, *, start: int = 1) -> str:
    """Convert SQLite `?` bind markers to provider-specific placeholders.

    Literal question marks inside single-quoted strings are preserved. The helper
    intentionally stays small and explicit; it does not attempt full SQL parsing.
    """
    if provider == SQLITE_PROVIDER:
        return sql
    if provider != POSTGRES_PROVIDER:
        raise ValueError(f"Unsupported database provider: {provider}")

    parts: list[str] = []
    in_single_quote = False
    placeholder_index = start
    position = 0
    while position < len(sql):
        character = sql[position]
        if character == "'":
            parts.append(character)
            if position + 1 < len(sql) and sql[position + 1] == "'":
                parts.append(sql[position + 1])
                position += 2
                continue
            in_single_quote = not in_single_quote
            position += 1
            continue
        if character == "?" and not in_single_quote:
            parts.append(placeholder(placeholder_index, POSTGRES_PROVIDER))
            placeholder_index += 1
            position += 1
            continue
        parts.append(character)
        position += 1
    return "".join(parts)


def append_returning_id(sql: str, provider: str) -> str:
    if provider == SQLITE_PROVIDER:
        return sql
    if provider != POSTGRES_PROVIDER:
        raise ValueError(f"Unsupported database provider: {provider}")
    stripped = sql.rstrip()
    if stripped.rstrip(";").lower().endswith("returning id"):
        return sql
    suffix = ";" if stripped.endswith(";") else ""
    body = stripped[:-1].rstrip() if suffix else stripped
    return f"{body} RETURNING id{suffix}"


def bind_values(*groups: Iterable[object]) -> tuple[object, ...]:
    values: list[object] = []
    for group in groups:
        values.extend(group)
    return tuple(values)


def inserted_id(cursor, provider: str) -> int:
    if provider == SQLITE_PROVIDER:
        return int(cursor.lastrowid)
    if provider == POSTGRES_PROVIDER:
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("Postgres INSERT ... RETURNING id did not return a row")
        if isinstance(row, dict):
            return int(row["id"])
        try:
            return int(row["id"])
        except (TypeError, KeyError, IndexError):
            return int(row[0])
    raise ValueError(f"Unsupported database provider: {provider}")

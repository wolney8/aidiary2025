"""Build bounded, user-scoped context for the diary chat companion."""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from services.database import connect_sqlite_path, table_columns


DEFAULT_CONTEXT_TOKEN_BUDGET = 3000
DEFAULT_RECENT_ENTRY_LIMIT = 20
MAX_ENTRY_BODY_CHARS = 600


@dataclass(frozen=True)
class _ContextEntry:
    mode: str
    entry_date: str
    entry_number: int
    title: str
    body: str
    tags: str
    people: str


def estimate_tokens(text: str) -> int:
    """Return a conservative dependency-free token estimate."""
    return math.ceil(len(text) / 4)


def _compact_text(value: object, max_chars: int = MAX_ENTRY_BODY_CHARS) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if len(text) <= max_chars:
        return text
    return f'{text[:max_chars - 1].rstrip()}…'


def _csv_values(raw: str) -> Iterable[str]:
    for value in str(raw or '').split(','):
        cleaned = re.sub(r'\s+', ' ', value).strip()
        if cleaned:
            yield cleaned


class ChatContextService:
    """Assemble prompt context without crossing user or token boundaries."""

    def __init__(
        self,
        database_path: str,
        *,
        token_budget: int = DEFAULT_CONTEXT_TOKEN_BUDGET,
        recent_entry_limit: int = DEFAULT_RECENT_ENTRY_LIMIT,
    ) -> None:
        if token_budget < 100:
            raise ValueError('token_budget must be at least 100')
        if recent_entry_limit < 1:
            raise ValueError('recent_entry_limit must be positive')
        self.database_path = database_path
        self.token_budget = token_budget
        self.recent_entry_limit = recent_entry_limit

    def build_context(self, user_id: int) -> str:
        """Build profile, theme, and recent-entry context for one user."""
        with connect_sqlite_path(self.database_path, timeout=10) as conn:
            identity = self._load_identity(conn, user_id)
            entries = self._load_recent_entries(conn, user_id)

        sections = [
            'Use this private diary context only when it is relevant. Do not invent '
            'details or mention system/database terminology.',
        ]
        if identity:
            sections.append(f'User context:\n{identity}')

        themes = self._build_theme_summary(entries)
        if themes:
            sections.append(f'Recurring context:\n{themes}')

        prefix = '\n\n'.join(sections)
        if estimate_tokens(prefix) >= self.token_budget:
            return self._fit_to_budget(prefix)

        included_entries: list[str] = []
        for entry in entries:
            entry_text = self._format_entry(entry)
            candidate_sections = [prefix]
            if included_entries:
                candidate_sections.append('Recent diary entries:\n' + '\n'.join(included_entries))
            candidate_sections.append(entry_text)
            if estimate_tokens('\n\n'.join(candidate_sections)) > self.token_budget:
                continue
            included_entries.append(entry_text)

        if included_entries:
            sections.append('Recent diary entries:\n' + '\n'.join(included_entries))

        return self._fit_to_budget('\n\n'.join(sections))

    def build_system_prompt(self, user_id: int) -> str:
        """Return the companion instructions and bounded private context."""
        context = self.build_context(user_id)
        prompt = (
            'You are a supportive AI diary companion. Respond with empathy, '
            'specificity, and practical perspective without diagnosing the user. '
            'Use prior diary details selectively and acknowledge uncertainty.\n\n'
            f'{context}'
        )
        return self._fit_to_budget(prompt)

    def _load_identity(self, conn: sqlite3.Connection, user_id: int) -> str:
        if not self._table_exists(conn, 'users'):
            return ''
        columns = self._table_columns(conn, 'users')
        permitted = [
            column for column in (
                'display_name',
                'first_name',
                'pronouns',
                'gender',
                'custom_guidance',
            )
            if column in columns
        ]
        if not permitted:
            return ''

        row = conn.execute(
            f"SELECT {', '.join(permitted)} FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return ''

        display_name = ''
        if 'display_name' in permitted:
            display_name = _compact_text(row['display_name'], 40)
        if not display_name and 'first_name' in permitted:
            display_name = _compact_text(row['first_name'], 40)

        values = []
        if display_name:
            values.append(f'Name: {display_name}')
        for column, label in (
            ('pronouns', 'Pronouns'),
            ('gender', 'Gender'),
            ('custom_guidance', 'Personal guidance'),
        ):
            if column in permitted and row[column]:
                values.append(f'{label}: {_compact_text(row[column], 160)}')
        return '\n'.join(values)

    def _load_recent_entries(
        self,
        conn: sqlite3.Connection,
        user_id: int,
    ) -> list[_ContextEntry]:
        entries: list[_ContextEntry] = []
        if self._table_exists(conn, 'dailydiary_entries'):
            rows = conn.execute(
                """
                SELECT entry_date, COALESCE(entry_number, 0) AS entry_number,
                       COALESCE(title, '') AS title,
                       COALESCE(user_message, '') AS body,
                       COALESCE(tags, '') AS tags,
                       COALESCE(daily_people_names, '') AS people
                FROM dailydiary_entries
                WHERE user_id = ?
                ORDER BY entry_date DESC, entry_number DESC, id DESC
                LIMIT ?
                """,
                (user_id, self.recent_entry_limit),
            ).fetchall()
            entries.extend(self._rows_to_entries('Daily', rows))

        if self._table_exists(conn, 'dreamdiary_entries'):
            rows = conn.execute(
                """
                SELECT entry_date, COALESCE(entry_number, 0) AS entry_number,
                       COALESCE(title, '') AS title,
                       COALESCE(NULLIF(summary, ''), plot, '') AS body,
                       COALESCE(tags, '') AS tags,
                       COALESCE(dream_people_names, '') AS people
                FROM dreamdiary_entries
                WHERE user_id = ?
                ORDER BY entry_date DESC, entry_number DESC, id DESC
                LIMIT ?
                """,
                (user_id, self.recent_entry_limit),
            ).fetchall()
            entries.extend(self._rows_to_entries('Dream', rows))

        entries.sort(key=lambda item: (item.entry_date, item.entry_number), reverse=True)
        return entries[:self.recent_entry_limit]

    @staticmethod
    def _rows_to_entries(mode: str, rows: Iterable[sqlite3.Row]) -> list[_ContextEntry]:
        return [
            _ContextEntry(
                mode=mode,
                entry_date=str(row['entry_date'] or ''),
                entry_number=int(row['entry_number'] or 0),
                title=_compact_text(row['title'], 120),
                body=_compact_text(row['body']),
                tags=str(row['tags'] or ''),
                people=str(row['people'] or ''),
            )
            for row in rows
        ]

    @staticmethod
    def _build_theme_summary(entries: list[_ContextEntry]) -> str:
        tags = Counter(value.casefold() for entry in entries for value in _csv_values(entry.tags))
        people = Counter(value.casefold() for entry in entries for value in _csv_values(entry.people))

        lines = []
        if tags:
            lines.append('Frequent themes: ' + ', '.join(value for value, _ in tags.most_common(8)))
        if people:
            lines.append('Frequently mentioned people: ' + ', '.join(value for value, _ in people.most_common(6)))
        return '\n'.join(lines)

    @staticmethod
    def _format_entry(entry: _ContextEntry) -> str:
        title = entry.title or 'Untitled entry'
        body = entry.body or 'No entry text saved.'
        return f'- {entry.entry_date} | {entry.mode} | {title}: {body}'

    def _fit_to_budget(self, text: str) -> str:
        max_chars = self.token_budget * 4
        if len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip()

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone() is not None

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
        return table_columns(conn, table_name)

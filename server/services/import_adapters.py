"""Provider adapters that map external diary exports to the import contract."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Protocol


class ImportAdapter(Protocol):
    source: str
    extensions: frozenset[str]
    mime_types: frozenset[str]

    def parse(self, file_bytes: bytes, *, filename: str) -> dict: ...


def _clean(value: object) -> str:
    text = str(value or '').strip()
    if text.startswith(('=', '+', '-', '@')):
        text = text[1:].lstrip()
    return re.sub(r'[<>]|javascript:', '', text, flags=re.IGNORECASE)


def _normalise_header(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', value.strip().lower()).strip('_')


def _first(row: dict[str, str], *keys: str) -> str:
    return next((_clean(row.get(key)) for key in keys if _clean(row.get(key))), '')


def _parse_date(value: str) -> str | None:
    for fmt in (
        '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y',
        '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
    ):
        try:
            return datetime.strptime(value.strip(), fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _parse_time(value: str) -> str:
    if not value.strip():
        return '19:00'
    for fmt in ('%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M:%S %p'):
        try:
            return datetime.strptime(value.strip(), fmt).strftime('%H:%M')
        except ValueError:
            continue
    return ''


def _normalise_activities(value: str) -> str:
    values = [item.strip() for item in re.split(r'[,;|]', value) if item.strip()]
    return ','.join(dict.fromkeys(values))


class DaylioCsvAdapter:
    source = 'daylio'
    extensions = frozenset({'.csv'})
    mime_types = frozenset({'text/csv', 'application/csv', 'text/plain', 'application/vnd.ms-excel'})

    def parse(self, file_bytes: bytes, *, filename: str) -> dict:
        try:
            text = file_bytes.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode('utf-16')
            except UnicodeDecodeError as exc:
                raise ValueError('Daylio CSV must use UTF-8 or UTF-16 text encoding.') from exc

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError('Daylio CSV has no header row.')

        normalised_headers = [_normalise_header(name) for name in reader.fieldnames]
        if not {'full_date', 'date'}.intersection(normalised_headers):
            raise ValueError('Daylio CSV must contain a date or full_date column.')

        daily_rows: list[dict[str, str]] = []
        warnings: list[str] = []
        for row_index, source_row in enumerate(reader, start=2):
            row = {
                _normalise_header(key): value
                for key, value in source_row.items()
                if key is not None
            }
            raw_date = _first(row, 'full_date', 'date')
            entry_date = _parse_date(raw_date)
            if not entry_date:
                warnings.append(f'Daylio row {row_index}: skipped - invalid or missing date.')
                continue

            entry_time = _parse_time(_first(row, 'time', 'entry_time'))
            if not entry_time:
                warnings.append(f'Daylio row {row_index}: skipped - invalid time.')
                continue

            mood = _first(row, 'mood', 'mood_name')
            activities = _normalise_activities(_first(row, 'activities', 'activity'))
            note = _first(row, 'note', 'notes', 'entry', 'text')
            title = _first(row, 'note_title', 'title')
            if not title:
                title = f'Daylio - {mood}' if mood else 'Daylio entry'

            if not note:
                context = []
                if mood:
                    context.append(f'Mood: {mood}')
                if activities:
                    context.append(f'Activities: {activities.replace(",", ", ")}')
                note = '\n'.join(context)
            if not note:
                warnings.append(f'Daylio row {row_index}: skipped - no note, mood, or activities.')
                continue

            daily_rows.append({
                'entry_date': entry_date,
                'entry_time': entry_time,
                'title': title,
                'user_message': note,
                'ai_response': '',
                'tags': activities,
                'mood': mood,
                'entry_asset_ref': '',
            })

        return {
            'daily': daily_rows,
            'dreams': [],
            'errors': [],
            'warnings': warnings,
        }


_ADAPTERS: dict[str, ImportAdapter] = {
    DaylioCsvAdapter.source: DaylioCsvAdapter(),
}


def get_import_adapter(source: str) -> ImportAdapter | None:
    return _ADAPTERS.get(source.strip().lower())


def supported_import_sources() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))

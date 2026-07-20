"""Provider adapters that map external diary exports to the import contract."""

from __future__ import annotations

import base64
import csv
import html
import io
import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Protocol


_DAYLIO_BACKUP_PAYLOAD = 'backup.daylio'
_DAYLIO_MAX_ARCHIVE_MEMBERS = 2000
_DAYLIO_MAX_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
_DAYLIO_MAX_PAYLOAD_BYTES = 25 * 1024 * 1024
_DAYLIO_MAX_PHOTO_BYTES = 10 * 1024 * 1024


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


def _clean_daylio_text(value: object) -> str:
    """Convert Daylio's occasional HTML notes to readable plain text."""
    text = html.unescape(str(value or ''))
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|div|li)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s*\n\s*', '\n', text)
    return _clean(text.strip())


def _first_daylio_text(row: dict[str, str], *keys: str) -> str:
    return next(
        (cleaned for key in keys if (cleaned := _clean_daylio_text(row.get(key)))),
        '',
    )


def _normalise_header(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', value.strip().lower()).strip('_')


def _first(row: dict[str, str], *keys: str) -> str:
    return next((_clean(row.get(key)) for key in keys if _clean(row.get(key))), '')


def _parse_date(value: str) -> str | None:
    for fmt in (
        '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y',
        '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M',
    ):
        try:
            return datetime.strptime(value.strip(), fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def _parse_time(value: str, *, fallback_datetime: str = '') -> str:
    for fmt in ('%H:%M', '%H:%M:%S', '%I:%M %p', '%I:%M:%S %p'):
        try:
            return datetime.strptime(value.strip(), fmt).strftime('%H:%M')
        except ValueError:
            continue
    for fmt in (
        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M',
    ):
        try:
            return datetime.strptime(fallback_datetime.strip(), fmt).strftime('%H:%M')
        except ValueError:
            continue
    if not value.strip():
        return '19:00'
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

        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ValueError('Daylio CSV has no header row.')

        normalised_headers = [_normalise_header(name) for name in reader.fieldnames]
        if not {'full_date', 'date'}.intersection(normalised_headers):
            raise ValueError('Daylio CSV must contain a date or full_date column.')

        daily_rows: list[dict[str, str]] = []
        warnings: list[str] = []
        mood_only_count = 0
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

            entry_time = _parse_time(
                _first(row, 'time', 'entry_time'),
                fallback_datetime=raw_date,
            )
            if not entry_time:
                warnings.append(f'Daylio row {row_index}: skipped - invalid time.')
                continue

            mood = _first(row, 'mood', 'mood_name')
            activities = _normalise_activities(_first(row, 'activities', 'activity'))
            note = _first_daylio_text(row, 'note', 'notes', 'entry', 'text')
            if not note:
                mood_only_count += 1
                continue
            title = _first_daylio_text(row, 'note_title', 'title')
            if not title:
                title = mood.capitalize() if mood else 'Imported entry'

            daily_rows.append({
                'entry_date': entry_date,
                'entry_time': entry_time,
                'title': title,
                'user_message': note,
                'ai_response': '',
                'tags': activities,
                'mood': mood,
                'source_app': 'daylio',
                'source_record_kind': 'authored',
                'entry_asset_ref': '',
            })

        if mood_only_count:
            warnings.append(
                f'Skipped {mood_only_count} Daylio mood/activity check-ins without authored notes.'
            )
        return {
            'daily': daily_rows,
            'dreams': [],
            'errors': [],
            'warnings': warnings,
        }


class DaylioBackupAdapter:
    """Parse Daylio's native ZIP backup without extracting untrusted paths."""

    def parse(self, file_bytes: bytes, *, filename: str) -> dict:
        try:
            archive = zipfile.ZipFile(io.BytesIO(file_bytes))
        except zipfile.BadZipFile as exc:
            raise ValueError('The Daylio backup is not a valid .daylio archive.') from exc

        with archive:
            members = archive.infolist()
            if len(members) > _DAYLIO_MAX_ARCHIVE_MEMBERS:
                raise ValueError('The Daylio backup contains too many files.')
            if sum(member.file_size for member in members) > _DAYLIO_MAX_UNCOMPRESSED_BYTES:
                raise ValueError('The expanded Daylio backup exceeds the safe import limit.')
            if _DAYLIO_BACKUP_PAYLOAD not in archive.namelist():
                raise ValueError('The Daylio backup does not contain backup.daylio.')

            payload_info = archive.getinfo(_DAYLIO_BACKUP_PAYLOAD)
            if payload_info.file_size > _DAYLIO_MAX_PAYLOAD_BYTES:
                raise ValueError('The Daylio backup data exceeds the safe import limit.')

            backup = self._decode_payload(archive.read(payload_info))
            return self._parse_backup(backup, archive)

    @staticmethod
    def _decode_payload(payload: bytes) -> dict:
        try:
            decoded = base64.b64decode(b''.join(payload.split()), validate=True)
            backup = json.loads(decoded.decode('utf-8'))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('The Daylio backup data could not be decoded.') from exc
        if not isinstance(backup, dict) or not isinstance(backup.get('dayEntries'), list):
            raise ValueError('The Daylio backup has an unsupported data structure.')
        return backup

    def _parse_backup(self, backup: dict, archive: zipfile.ZipFile) -> dict:
        moods = {
            item.get('id'): _clean(item.get('custom_name'))
            for item in backup.get('customMoods', [])
            if isinstance(item, dict)
        }
        tags = {
            item.get('id'): _clean(item.get('name'))
            for item in backup.get('tags', [])
            if isinstance(item, dict)
        }
        assets = {
            item.get('id'): item
            for item in backup.get('assets', [])
            if isinstance(item, dict)
        }
        photo_members = {
            Path(name).name: name
            for name in archive.namelist()
            if name.startswith('assets/photos/') and not name.endswith('/')
        }

        daily_rows: list[dict] = []
        warnings: list[str] = []
        mood_only_count = 0
        staging_root: str | None = None
        try:
            for row_index, source_row in enumerate(backup['dayEntries'], start=1):
                if not isinstance(source_row, dict):
                    warnings.append(f'Daylio entry {row_index}: skipped - invalid entry data.')
                    continue

                entry_date = self._entry_date(source_row)
                entry_time = self._entry_time(source_row)
                if not entry_date or not entry_time:
                    warnings.append(f'Daylio entry {row_index}: skipped - invalid date or time.')
                    continue

                mood = moods.get(source_row.get('mood'), '')
                source_tag_ids = source_row.get('tags', [])
                if not isinstance(source_tag_ids, list):
                    source_tag_ids = []
                activity_names = [tags.get(tag_id, '') for tag_id in source_tag_ids]
                activities = ','.join(dict.fromkeys(name for name in activity_names if name))
                note = _clean_daylio_text(source_row.get('note'))
                if not note:
                    mood_only_count += 1
                    continue
                title = _clean_daylio_text(source_row.get('note_title'))
                if not title:
                    title = mood.capitalize() if mood else 'Imported entry'

                row = {
                    'entry_date': entry_date,
                    'entry_time': entry_time,
                    'title': title,
                    'user_message': note,
                    'ai_response': '',
                    'tags': activities,
                    'mood': mood,
                    'source_app': 'daylio',
                    'source_record_kind': 'authored',
                    'entry_asset_ref': '',
                }
                attachment_files, staging_root = self._stage_entry_photos(
                    source_row.get('assets', []),
                    assets=assets,
                    photo_members=photo_members,
                    archive=archive,
                    staging_root=staging_root,
                    row_index=row_index,
                    warnings=warnings,
                )
                if attachment_files:
                    row['import_attachment_files'] = attachment_files
                daily_rows.append(row)
        except Exception:
            if staging_root:
                shutil.rmtree(staging_root, ignore_errors=True)
            raise

        if mood_only_count:
            warnings.append(
                f'Skipped {mood_only_count} Daylio mood/activity check-ins without authored notes.'
            )
        result = {
            'daily': daily_rows,
            'dreams': [],
            'errors': [],
            'warnings': warnings,
        }
        if staging_root:
            result['package_staging_root'] = staging_root
        return result

    @staticmethod
    def _entry_date(row: dict) -> str:
        try:
            # Daylio stores January as month 0 in native iOS backups.
            return datetime(
                int(row['year']), int(row['month']) + 1, int(row['day'])
            ).strftime('%Y-%m-%d')
        except (KeyError, TypeError, ValueError):
            return ''

    @staticmethod
    def _entry_time(row: dict) -> str:
        try:
            return datetime(2000, 1, 1, int(row['hour']), int(row['minute'])).strftime('%H:%M')
        except (KeyError, TypeError, ValueError):
            return ''

    @staticmethod
    def _stage_entry_photos(
        asset_ids: object,
        *,
        assets: dict,
        photo_members: dict[str, str],
        archive: zipfile.ZipFile,
        staging_root: str | None,
        row_index: int,
        warnings: list[str],
    ) -> tuple[list[dict[str, str | int]], str | None]:
        if not isinstance(asset_ids, list):
            return [], staging_root

        staged: list[dict[str, str | int]] = []
        for sort_order, asset_id in enumerate(asset_ids[:3]):
            asset = assets.get(asset_id)
            checksum = str(asset.get('checksum') or '').strip() if asset else ''
            member_name = photo_members.get(checksum)
            if not member_name:
                warnings.append(f'Daylio entry {row_index}: referenced photo was not found.')
                continue

            member = archive.getinfo(member_name)
            if member.file_size > _DAYLIO_MAX_PHOTO_BYTES:
                warnings.append(f'Daylio entry {row_index}: skipped a photo larger than 10 MB.')
                continue
            photo_bytes = archive.read(member)
            if not photo_bytes.startswith(b'\xff\xd8\xff'):
                warnings.append(f'Daylio entry {row_index}: skipped an unsupported photo format.')
                continue

            if staging_root is None:
                staging_root = tempfile.mkdtemp(prefix='aidiary-daylio-import-')
            entry_dir = Path(staging_root) / f'entry-{row_index}'
            entry_dir.mkdir(parents=True, exist_ok=True)
            filename = f'daylio-photo-{asset_id}.jpg'
            staged_path = entry_dir / filename
            staged_path.write_bytes(photo_bytes)
            staged.append({
                'staged_path': str(staged_path),
                'original_filename': filename,
                'mime_type': 'image/jpeg',
                'asset_role': 'attachment',
                'sort_order': sort_order,
                'file_size_bytes': len(photo_bytes),
            })

        if len(asset_ids) > 3:
            warnings.append(
                f'Daylio entry {row_index}: imported the first 3 photos; extra photos exceeded the entry limit.'
            )
        return staged, staging_root


class DaylioAdapter:
    source = 'daylio'
    extensions = frozenset({'.csv', '.daylio'})
    mime_types = frozenset({
        'text/csv',
        'application/csv',
        'text/plain',
        'application/vnd.ms-excel',
        'application/octet-stream',
        'application/zip',
        'application/x-zip-compressed',
    })

    def __init__(self) -> None:
        self.csv_adapter = DaylioCsvAdapter()
        self.backup_adapter = DaylioBackupAdapter()

    def parse(self, file_bytes: bytes, *, filename: str) -> dict:
        if filename.lower().endswith('.daylio'):
            return self.backup_adapter.parse(file_bytes, filename=filename)
        return self.csv_adapter.parse(file_bytes, filename=filename)


_ADAPTERS: dict[str, ImportAdapter] = {
    DaylioAdapter.source: DaylioAdapter(),
}


def get_import_adapter(source: str) -> ImportAdapter | None:
    return _ADAPTERS.get(source.strip().lower())


def supported_import_sources() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))

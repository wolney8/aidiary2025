"""Audit database media references against the configured media store.

The cloud database cutover only moves relational data. Entry images, profile
images, and attachments are stored behind portable storage keys, so a production
cutover must also prove that those keys resolve in the active media backend.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from services.database import resolve_database_settings
from services.database_adapter import DatabaseAdapter


MEDIA_REFERENCE_SOURCES = [
    {
        "source": "profile_images",
        "table": "users",
        "key_column": "profile_picture_storage_key",
        "select_columns": {
            "record_id": "id",
            "user_id": "id",
        },
    },
    {
        "source": "daily_images",
        "table": "dailydiary_entries",
        "key_column": "image_storage_key",
        "select_columns": {
            "record_id": "id",
            "user_id": "user_id",
        },
    },
    {
        "source": "dream_images",
        "table": "dreamdiary_entries",
        "key_column": "image_storage_key",
        "select_columns": {
            "record_id": "id",
            "user_id": "user_id",
        },
    },
    {
        "source": "important_day_images",
        "table": "important_days",
        "key_column": "image_storage_key",
        "select_columns": {
            "record_id": "id",
            "user_id": "user_id",
        },
    },
    {
        "source": "entry_assets",
        "table": "entry_assets",
        "key_column": "storage_key",
        "select_columns": {
            "record_id": "id",
            "user_id": "user_id",
            "entry_type": "entry_type",
            "entry_id": "entry_id",
            "filename": "original_filename",
        },
    },
]


def _row_value(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return None


def _storage_key_to_path(media_root: Path, storage_key: str) -> Path:
    posix_key = PurePosixPath(storage_key)
    if posix_key.is_absolute() or ".." in posix_key.parts:
        raise ValueError("Invalid media storage key.")
    return media_root.joinpath(*posix_key.parts)


def _build_media_query(source: dict[str, Any]) -> str:
    selected = [
        f"{column} AS {alias}"
        for alias, column in source["select_columns"].items()
    ]
    selected.append(f"{source['key_column']} AS storage_key")
    return (
        f"SELECT {', '.join(selected)} "
        f"FROM {source['table']} "
        f"WHERE {source['key_column']} IS NOT NULL "
        f"AND TRIM({source['key_column']}) <> '' "
        f"ORDER BY {source['select_columns']['record_id']}"
    )


def _empty_source_report(source: str, *, status: str, reason: str | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "source": source,
        "status": status,
        "checked": 0,
        "present": 0,
        "missing": 0,
        "invalid": 0,
    }
    if reason:
        report["reason"] = reason
    return report


def audit_media_storage(
    *,
    adapter: DatabaseAdapter,
    media_root: Path,
    max_details: int = 50,
) -> dict[str, Any]:
    media_root = media_root.expanduser().resolve()
    sources: list[dict[str, Any]] = []
    missing_details: list[dict[str, Any]] = []
    invalid_details: list[dict[str, Any]] = []
    total_checked = 0
    total_present = 0
    total_missing = 0
    total_invalid = 0

    with adapter.connect() as conn:
        for source in MEDIA_REFERENCE_SOURCES:
            source_name = str(source["source"])
            table_name = str(source["table"])
            key_column = str(source["key_column"])

            if not adapter.table_exists(conn, table_name):
                sources.append(
                    _empty_source_report(
                        source_name,
                        status="skipped",
                        reason=f"table missing: {table_name}",
                    )
                )
                continue

            table_columns = adapter.table_columns(conn, table_name)
            required_columns = {
                key_column,
                *source["select_columns"].values(),
            }
            missing_columns = sorted(required_columns - table_columns)
            if missing_columns:
                sources.append(
                    _empty_source_report(
                        source_name,
                        status="skipped",
                        reason=f"columns missing: {', '.join(missing_columns)}",
                    )
                )
                continue

            rows = conn.execute(_build_media_query(source)).fetchall()
            source_checked = 0
            source_present = 0
            source_missing = 0
            source_invalid = 0

            for row in rows:
                storage_key = str(_row_value(row, "storage_key") or "").strip()
                if not storage_key:
                    continue

                detail = {
                    "source": source_name,
                    "table": table_name,
                    "record_id": _row_value(row, "record_id"),
                    "user_id": _row_value(row, "user_id"),
                    "storage_key": storage_key,
                }
                for optional_key in ("entry_type", "entry_id", "filename"):
                    value = _row_value(row, optional_key)
                    if value is not None:
                        detail[optional_key] = value

                source_checked += 1
                try:
                    media_path = _storage_key_to_path(media_root, storage_key)
                except ValueError as exc:
                    source_invalid += 1
                    if len(invalid_details) < max_details:
                        invalid_details.append({**detail, "reason": str(exc)})
                    continue

                if media_path.exists():
                    source_present += 1
                else:
                    source_missing += 1
                    if len(missing_details) < max_details:
                        missing_details.append(detail)

            sources.append(
                {
                    "source": source_name,
                    "status": "checked",
                    "checked": source_checked,
                    "present": source_present,
                    "missing": source_missing,
                    "invalid": source_invalid,
                }
            )
            total_checked += source_checked
            total_present += source_present
            total_missing += source_missing
            total_invalid += source_invalid

    return {
        "ready_for_cutover": total_missing == 0 and total_invalid == 0,
        "provider": adapter.provider,
        "media_root": str(media_root),
        "summary": {
            "references_checked": total_checked,
            "present": total_present,
            "missing": total_missing,
            "invalid": total_invalid,
            "missing_details_returned": len(missing_details),
            "invalid_details_returned": len(invalid_details),
        },
        "sources": sources,
        "missing": missing_details,
        "invalid": invalid_details,
    }


def _default_media_root(server_root: Path) -> Path:
    return Path(os.getenv("MEDIA_ROOT") or server_root / "media")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit database media references against MEDIA_ROOT."
    )
    parser.add_argument(
        "--media-root",
        default=None,
        help="Media root to audit. Defaults to MEDIA_ROOT or server/media.",
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=50,
        help="Maximum missing/invalid reference details to include in output.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write the audit JSON report.",
    )
    args = parser.parse_args()

    server_root = Path(__file__).resolve().parents[1]
    settings = resolve_database_settings(str(server_root))
    report = audit_media_storage(
        adapter=DatabaseAdapter.from_settings(settings),
        media_root=Path(args.media_root).expanduser() if args.media_root else _default_media_root(server_root),
        max_details=max(args.max_details, 0),
    )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    print(output)
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    return 0 if report["ready_for_cutover"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

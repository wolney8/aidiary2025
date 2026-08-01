"""Export a managed Postgres snapshot to the migration JSONL format.

Use this after cloud cutover acceptance to keep provider-portable local snapshots. The
export is read-only and writes files under an operator-provided directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from scripts.load_cloud_migration import _quote_identifier
from scripts.rehearse_cloud_migration import TABLE_ORDER
from services.database import POSTGRES_PROVIDER
from services.database_adapter import DatabaseAdapter


DEFAULT_SNAPSHOT_DIR = Path.home() / "OpenMyndBackups" / "postgres-snapshots"


class SnapshotAdapter(Protocol):
    provider: str

    def connect(self, *, timeout: int = 30): ...

    def table_exists(self, conn, table_name: str) -> bool: ...

    def table_columns(self, conn, table_name: str) -> set[str]: ...


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_name(label: str) -> str:
    safe_label = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in label.strip()
    ).strip("-_") or "snapshot"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"postgres-{timestamp}-{safe_label}"


def _next_snapshot_dir(output_dir: Path, label: str) -> Path:
    base_name = _snapshot_name(label)
    candidate = output_dir / base_name
    suffix = 2
    while candidate.exists():
        candidate = output_dir / f"{base_name}-{suffix}"
        suffix += 1
    return candidate


def _order_by_clause(columns: set[str]) -> str:
    if "id" in columns:
        return " ORDER BY \"id\""
    if "worksheet_id" in columns:
        return " ORDER BY \"worksheet_id\""
    return ""


def export_postgres_snapshot(
    *,
    adapter: SnapshotAdapter,
    output_dir: Path,
    label: str = "snapshot",
) -> dict[str, Any]:
    if adapter.provider != POSTGRES_PROVIDER:
        raise ValueError("Postgres snapshot export requires DATABASE_PROVIDER=postgres")

    output_dir = output_dir.expanduser().resolve()
    snapshot_dir = _next_snapshot_dir(output_dir, label)
    snapshot_dir.mkdir(parents=True, exist_ok=False)

    manifest_tables: list[dict[str, Any]] = []
    with adapter.connect(timeout=30) as conn:
        for table_name in TABLE_ORDER:
            if not adapter.table_exists(conn, table_name):
                continue
            columns = adapter.table_columns(conn, table_name)
            output_path = snapshot_dir / f"{table_name}.jsonl"
            quoted_table = _quote_identifier(table_name)
            rows = conn.execute(
                f"SELECT * FROM {quoted_table}{_order_by_clause(columns)}"
            ).fetchall()
            with output_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(dict(row), ensure_ascii=False, default=str))
                    handle.write("\n")
            manifest_tables.append(
                {
                    "table": table_name,
                    "file": output_path.name,
                    "row_count": len(rows),
                    "byte_size": output_path.stat().st_size,
                    "sha256": _sha256_file(output_path),
                }
            )

    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": POSTGRES_PROVIDER,
        "snapshot_dir": str(snapshot_dir),
        "label": label,
        "tables": manifest_tables,
        "total_rows": sum(table["row_count"] for table in manifest_tables),
    }
    manifest_path = snapshot_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export a Postgres snapshot to JSONL files with a manifest."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL") or "",
        help="Postgres connection URL. Defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("POSTGRES_SNAPSHOT_DIR") or str(DEFAULT_SNAPSHOT_DIR),
        help="Directory that will contain timestamped snapshot subdirectories.",
    )
    parser.add_argument(
        "--label",
        default=os.getenv("POSTGRES_SNAPSHOT_LABEL") or "scheduled",
        help="Short label included in the snapshot directory name.",
    )
    parser.add_argument("--output-json", help="Optional path for a copy of the manifest.")
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("DATABASE_URL is required for Postgres snapshot export.")

    manifest = export_postgres_snapshot(
        adapter=DatabaseAdapter(
            provider=POSTGRES_PROVIDER,
            sqlite_path="",
            database_url=args.database_url,
        ),
        output_dir=Path(args.output_dir),
        label=args.label,
    )
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

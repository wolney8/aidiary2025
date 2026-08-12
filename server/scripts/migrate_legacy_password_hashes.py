"""Audit or migrate legacy plaintext password rows to bcrypt hashes."""

from __future__ import annotations

import argparse
import json

from app import create_app
from services.legacy_passwords import migrate_legacy_passwords


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit or migrate OpenMynd legacy plaintext password rows."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write bcrypt hashes back to the database. Omit for dry-run audit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a short text report.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        adapter = app.config["DATABASE_ADAPTER"]
        with adapter.connect(timeout=30) as conn:
            report = migrate_legacy_passwords(conn, apply=args.apply)

    payload = report.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        mode = "APPLY" if args.apply else "DRY RUN"
        print(f"Legacy password migration: {mode}")
        print(f"Users scanned: {payload['total_users_scanned']}")
        print(f"Legacy plaintext rows found: {payload['legacy_passwords_found']}")
        print(f"Migrated: {payload['migrated']}")
        print(f"Skipped empty passwords: {payload['skipped_empty_passwords']}")
        if not args.apply and payload["legacy_passwords_found"]:
            print("Run again with --apply to write bcrypt hashes.")

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

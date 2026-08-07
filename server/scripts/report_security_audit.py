"""Generate an operator security-audit report.

This is intentionally a local/ops command rather than an HTTP endpoint. OpenMynd
does not yet have admin roles, so exposing audit rows through the app would
create an avoidable authorization surface.
"""

from __future__ import annotations

import argparse
import json

from app import create_app
from services.security_audit_report import (
    build_security_audit_report,
    format_security_audit_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Report OpenMynd security audit events.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window. Use 0 for all time.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum recent events to include.")
    parser.add_argument("--event-type", help="Filter to one audit event type.")
    parser.add_argument("--outcome", help="Filter to one event outcome.")
    parser.add_argument("--user-id", type=int, help="Filter to one user id.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        adapter = app.config["DATABASE_ADAPTER"]
        with adapter.connect(timeout=15) as conn:
            report = build_security_audit_report(
                conn,
                database_provider=adapter.provider,
                days=args.days,
                limit=args.limit,
                event_type=args.event_type,
                outcome=args.outcome,
                user_id=args.user_id,
            )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_security_audit_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

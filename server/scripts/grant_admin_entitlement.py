"""Grant administrator entitlement to an existing OpenMynd user.

Use this for first-owner setup in local/staging environments. It updates OpenMynd's
local entitlement table; it does not change Stripe subscriptions.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from services.billing_entitlements import upsert_user_entitlement  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--email", help="User email to promote.")
    group.add_argument("--username", help="Username to promote.")
    group.add_argument("--user-id", type=int, help="User id to promote.")
    args = parser.parse_args()

    app = create_app()
    adapter = app.config["DATABASE_ADAPTER"]
    with adapter.connect(timeout=10) as conn:
        if args.user_id:
            row = conn.execute("SELECT id, email, username FROM users WHERE id = ?", (args.user_id,)).fetchone()
        elif args.email:
            row = conn.execute(
                "SELECT id, email, username FROM users WHERE lower(email) = lower(?)",
                (args.email.strip(),),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id, email, username FROM users WHERE lower(username) = lower(?)",
                (args.username.strip(),),
            ).fetchone()

        if row is None:
            print("No matching user found.")
            return 1

        user_id = int(row["id"] if isinstance(row, dict) else row[0])
        entitlement = upsert_user_entitlement(
            conn,
            user_id=user_id,
            tier="administrator",
            source="manual",
            status="active",
        )

    print(f"Granted administrator entitlement to user {user_id}: {entitlement['tier']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

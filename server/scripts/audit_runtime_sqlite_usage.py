"""Audit product runtime code for direct SQLite connection usage.

The cloud cutover path allows SQLite helpers and runtime migrations to remain
SQLite-specific, but product routes should use DatabaseAdapter.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


FORBIDDEN_PATTERNS = {
    "connect_sqlite_import": re.compile(r"from\s+services\.database\s+import\s+connect_sqlite\b"),
    "connect_sqlite_call": re.compile(r"\bconnect_sqlite\s*\("),
    "sqlite3_connect_call": re.compile(r"\bsqlite3\.connect\s*\("),
}

ALLOWED_RELATIVE_PATHS = {
    Path("server/app.py"),
    Path("server/services/database.py"),
    Path("server/services/runtime_migrations.py"),
}

SCAN_ROOTS = [
    Path("server/app.py"),
    Path("server/routes"),
    Path("server/services"),
]


def _iter_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        absolute_path = repo_root / scan_root
        if absolute_path.is_file():
            files.append(absolute_path)
            continue
        if absolute_path.is_dir():
            files.extend(sorted(absolute_path.rglob("*.py")))
    return files


def audit_runtime_sqlite_usage(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    violations: list[dict[str, object]] = []

    for file_path in _iter_python_files(repo_root):
        relative_path = file_path.relative_to(repo_root)
        if relative_path in ALLOWED_RELATIVE_PATHS:
            continue

        text = file_path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_name, pattern in FORBIDDEN_PATTERNS.items():
                if pattern.search(line):
                    violations.append(
                        {
                            "path": str(relative_path),
                            "line": line_number,
                            "pattern": pattern_name,
                            "text": line.strip(),
                        }
                    )

    return {
        "passed": not violations,
        "violations": violations,
        "allowlist": [str(path) for path in sorted(ALLOWED_RELATIVE_PATHS)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit runtime product code for direct SQLite connection usage."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[2],
        type=Path,
        help="Repository root to scan.",
    )
    args = parser.parse_args()

    report = audit_runtime_sqlite_usage(args.repo_root)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

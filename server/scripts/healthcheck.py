"""Dependency-free process healthcheck for OpenMynd API deployments."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _check_url(url: str, timeout: float) -> dict[str, object]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read(8192).decode("utf-8", errors="replace")
            body: object
            try:
                body = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                body = raw_body[:500]
            return {
                "url": url,
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "body": body,
            }
    except HTTPError as exc:
        return {"url": url, "ok": False, "status": exc.code, "error": str(exc)}
    except URLError as exc:
        return {"url": url, "ok": False, "status": None, "error": str(exc.reason)}
    except TimeoutError:
        return {"url": url, "ok": False, "status": None, "error": "timeout"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--database-write",
        action="store_true",
        help="Also verify database write readiness through the temporary write probe.",
    )
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    checks = [
        _check_url(f"{base_url}/health", args.timeout),
        _check_url(
            f"{base_url}/api/health/database{'?write=true' if args.database_write else ''}",
            args.timeout,
        ),
    ]
    report = {"ok": all(check["ok"] for check in checks), "checks": checks}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


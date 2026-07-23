"""Capture API latency and status baseline after a cloud database cutover."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from time import perf_counter
from typing import Any

import httpx


PUBLIC_ENDPOINTS = [
    ("health", "GET", "/health"),
    ("public_holiday_countries", "GET", "/api/public-holidays/countries"),
]

AUTH_ENDPOINTS = [
    ("profile", "GET", "/api/profile"),
    ("daily_entries", "GET", "/api/daily"),
    ("dream_entries", "GET", "/api/dreams"),
    ("important_days", "GET", "/api/important-days"),
    ("import_history", "GET", "/api/import/history"),
    ("reflection_summaries", "GET", "/api/reflection-summaries"),
    ("thought_records", "GET", "/api/cbt/worksheets"),
    ("on_this_day", "GET", "/api/on-this-day"),
    ("chat_observability", "GET", "/api/chat/observability/report?days=1"),
]


@dataclass(frozen=True)
class EndpointProbe:
    name: str
    method: str
    path: str
    requires_auth: bool


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * percentile), len(ordered) - 1)
    return ordered[index]


def _probe_endpoint(
    client: httpx.Client,
    probe: EndpointProbe,
    *,
    samples: int,
    token: str | None,
) -> dict[str, Any]:
    if probe.requires_auth and not token:
        return {
            "name": probe.name,
            "path": probe.path,
            "requires_auth": True,
            "skipped": True,
            "skip_reason": "auth token not supplied",
            "samples": [],
        }

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    samples_out = []
    for _ in range(samples):
        started = perf_counter()
        error = None
        status_code = None
        try:
            response = client.request(probe.method, probe.path, headers=headers)
            status_code = response.status_code
        except httpx.HTTPError as exc:
            error = str(exc)
        latency_ms = round((perf_counter() - started) * 1000)
        samples_out.append(
            {
                "status_code": status_code,
                "latency_ms": latency_ms,
                "error": error,
            }
        )

    latencies = [
        sample["latency_ms"]
        for sample in samples_out
        if sample["status_code"] is not None and sample["error"] is None
    ]
    errors = [
        sample
        for sample in samples_out
        if sample["error"] is not None
        or sample["status_code"] is None
        or int(sample["status_code"]) >= 500
    ]
    return {
        "name": probe.name,
        "path": probe.path,
        "requires_auth": probe.requires_auth,
        "skipped": False,
        "sample_count": len(samples_out),
        "ok_count": len(samples_out) - len(errors),
        "error_count": len(errors),
        "average_latency_ms": round(mean(latencies)) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "samples": samples_out,
    }


def capture_baseline(
    *,
    base_url: str,
    token: str | None = None,
    samples: int = 3,
    timeout_seconds: float = 10,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    bounded_samples = min(max(int(samples), 1), 20)
    close_client = client is None
    active_client = client or httpx.Client(
        base_url=base_url.rstrip("/"),
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    try:
        probes = [
            *(EndpointProbe(name, method, path, False) for name, method, path in PUBLIC_ENDPOINTS),
            *(EndpointProbe(name, method, path, True) for name, method, path in AUTH_ENDPOINTS),
        ]
        endpoint_results = [
            _probe_endpoint(active_client, probe, samples=bounded_samples, token=token)
            for probe in probes
        ]
    finally:
        if close_client:
            active_client.close()

    measured = [result for result in endpoint_results if not result.get("skipped")]
    errors = sum(int(result.get("error_count") or 0) for result in measured)
    samples_total = sum(int(result.get("sample_count") or 0) for result in measured)
    latencies = [
        sample["latency_ms"]
        for result in measured
        for sample in result["samples"]
        if sample["status_code"] is not None and sample["error"] is None
    ]
    return {
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": base_url.rstrip("/"),
        "samples_per_endpoint": bounded_samples,
        "authenticated": bool(token),
        "summary": {
            "measured_endpoints": len(measured),
            "skipped_endpoints": len(endpoint_results) - len(measured),
            "sample_count": samples_total,
            "error_count": errors,
            "average_latency_ms": round(mean(latencies)) if latencies else None,
            "p95_latency_ms": _percentile(latencies, 0.95),
        },
        "endpoints": endpoint_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture post-cutover API latency/status baseline."
    )
    parser.add_argument("--base-url", default="http://localhost:5001")
    parser.add_argument("--token", help="Optional JWT for authenticated endpoint probes.")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--output-json", help="Optional path to write JSON output.")
    args = parser.parse_args()

    report = capture_baseline(
        base_url=args.base_url,
        token=args.token,
        samples=args.samples,
        timeout_seconds=args.timeout_seconds,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        output_path = Path(args.output_json).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0 if report["summary"]["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

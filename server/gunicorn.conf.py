"""Gunicorn defaults for hosted OpenMynd API deployments.

Keep secrets in the environment. This file only contains process-shape defaults that
are safe to commit and can be overridden by platform environment variables.
"""

from __future__ import annotations

import multiprocessing
import os


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"
workers = _int_env(
    "WEB_CONCURRENCY",
    max(2, min((multiprocessing.cpu_count() * 2) + 1, 4)),
)
threads = _int_env("GUNICORN_THREADS", 4)
timeout = _int_env("GUNICORN_TIMEOUT", 120)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = _int_env("GUNICORN_KEEPALIVE", 5)
max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 100)

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")


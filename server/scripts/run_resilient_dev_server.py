"""Run the local Flask dev server with crash restart backoff.

This is a local-development guard only. Production should use a process manager
or platform supervisor around Gunicorn.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    port = os.environ.get("FLASK_PORT") or "5001"
    max_restarts = int(os.environ.get("OPENMYND_DEV_SERVER_MAX_RESTARTS", "20"))
    restart_count = 0
    backoff_seconds = 1
    command = [
        sys.executable,
        "-m",
        "flask",
        "--app",
        "app.py",
        "--debug",
        "run",
        "-p",
        port,
    ]

    stopping = False

    def stop(_signum, _frame) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    while not stopping:
        process = subprocess.Popen(command)
        while process.poll() is None and not stopping:
            time.sleep(0.25)
        if stopping:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            return 0

        exit_code = process.returncode
        if exit_code == 0:
            return 0

        restart_count += 1
        if restart_count > max_restarts:
            print(
                f"OpenMynd dev server stopped after {max_restarts} failed restarts.",
                file=sys.stderr,
            )
            return exit_code or 1

        print(
            f"OpenMynd dev server exited with {exit_code}; restarting in "
            f"{backoff_seconds}s ({restart_count}/{max_restarts}).",
            file=sys.stderr,
        )
        time.sleep(backoff_seconds)
        backoff_seconds = min(backoff_seconds * 2, 30)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

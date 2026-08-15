"""Vercel Python Function entrypoint for the OpenMynd Flask API.

This keeps the existing Flask app intact while allowing a single Vercel project to
route /api and /media requests to serverless Python during deployment rehearsals.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = REPO_ROOT / "server"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app import create_app  # noqa: E402


app = create_app()

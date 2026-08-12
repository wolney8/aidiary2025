#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== Backend: pytest =="
(
  cd "$ROOT_DIR/server"
  if [[ -f venv/bin/activate ]]; then
    # Local convenience only; CI installs dependencies explicitly.
    source venv/bin/activate
  fi
  PYTHONPATH=. pytest
)

echo "== Frontend: lint =="
(
  cd "$ROOT_DIR/client"
  npm run lint
)

echo "== Frontend: build =="
(
  cd "$ROOT_DIR/client"
  npm run build
)

if [[ "${RUN_E2E:-0}" == "1" ]]; then
  echo "== Browser: smoke =="
  (
    cd "$ROOT_DIR/client"
    npm run test:e2e:smoke
    npm run test:e2e:a11y
    npm run test:e2e:inactivity
    npm run test:e2e:cookie-auth
  )
else
  echo "== Browser: skipped =="
  echo "Set RUN_E2E=1 scripts/run_release_checks.sh to include Playwright gates."
fi

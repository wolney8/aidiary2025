#!/usr/bin/env bash
# lint-on-change.sh — Runs the project's configured linter on the modified file.
# Triggered by: PostToolUse
# Exit behaviour:
#   0  — no issues (or linter not configured — non-blocking)
#   2  — blocking lint errors found; agent must fix before proceeding

set -euo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input') or {}
print(ti.get('filePath') or ti.get('path') or ti.get('file_path') or '')
" 2>/dev/null || echo "")

[[ -z "$FILE" || ! -f "$FILE" ]] && exit 0

EXT="${FILE##*.}"
ERRORS=0

# ── JavaScript / TypeScript ────────────────────────────────────────────────────
if [[ "$EXT" =~ ^(js|jsx|ts|tsx|mjs|cjs)$ ]]; then
  if [[ -f "biome.json" ]]; then
    npx --no-install biome check "$FILE" 2>&1 || ERRORS=1
  elif ls eslint.config.* .eslintrc.* .eslintrc.json 2>/dev/null | grep -q .; then
    npx --no-install eslint "$FILE" 2>&1 || ERRORS=1
  fi
fi

# ── Python ─────────────────────────────────────────────────────────────────────
if [[ "$EXT" == "py" ]]; then
  if command -v ruff &>/dev/null; then
    ruff check "$FILE" 2>&1 || ERRORS=1
  elif command -v flake8 &>/dev/null; then
    flake8 "$FILE" 2>&1 || ERRORS=1
  fi
fi

# ── TypeScript type check (project-wide, only on .ts/.tsx) ────────────────────
if [[ "$EXT" =~ ^(ts|tsx)$ ]] && [[ -f "tsconfig.json" ]]; then
  npx --no-install tsc --noEmit 2>&1 || ERRORS=1
fi

[[ $ERRORS -ne 0 ]] && exit 2
exit 0

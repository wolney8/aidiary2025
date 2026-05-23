#!/usr/bin/env bash
# format-on-save.sh — Runs Prettier on the file modified by the previous edit operation.
# Triggered by: PostToolUse
# Exit behaviour: always exits 0 (non-blocking — formatting is best-effort).

set -euo pipefail

# Parse the modified file path from hook stdin JSON.
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input') or {}
# Copilot tools use 'filePath'; fallbacks for other conventions
print(ti.get('filePath') or ti.get('path') or ti.get('file_path') or '')
" 2>/dev/null || echo "")

# Nothing to do if no file was identified or the file does not exist.
[[ -z "$FILE" || ! -f "$FILE" ]] && exit 0

# Run Prettier if it is available (local install preferred over global).
if npx --no-install prettier --version &>/dev/null 2>&1 || command -v prettier &>/dev/null; then
  npx prettier --write --ignore-unknown "$FILE" 2>/dev/null || true
fi

exit 0

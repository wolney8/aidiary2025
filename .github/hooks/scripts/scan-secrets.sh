#!/usr/bin/env bash
# scan-secrets.sh — Scans edited files for hardcoded secrets and credential patterns.
# Triggered by: PostToolUse
# Exit behaviour:
#   0  — no secrets detected
#   2  — potential secret found (blocking — file must be cleaned before proceeding)

set -euo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input') or {}
print(ti.get('filePath') or ti.get('path') or ti.get('file_path') or '')
" 2>/dev/null || echo "")

[[ -z "$FILE" || ! -f "$FILE" ]] && exit 0

# Skip binary files, lock files, and media assets.
case "$FILE" in
  *.png|*.jpg|*.jpeg|*.gif|*.ico|*.svg|*.woff|*.woff2|*.ttf|*.eot) exit 0 ;;
  *.lock|*.sum|*.snap) exit 0 ;;
esac

# Skip .env.example and test fixtures — these intentionally contain placeholder values.
case "$(basename "$FILE")" in
  .env.example|.env.sample|*.test.*|*.spec.*|*.fixture.*) exit 0 ;;
esac

FOUND=false

# Pattern format: "LABEL|REGEX"
declare -a PATTERNS=(
  "OpenAI / Stripe secret key|sk-[a-zA-Z0-9]{32,}"
  "AWS access key ID|AKIA[0-9A-Z]{16}"
  "GitHub PAT (classic)|ghp_[a-zA-Z0-9]{36}"
  "GitHub app installation token|ghs_[a-zA-Z0-9]{36}"
  "GitHub OAuth token|gho_[a-zA-Z0-9]{36}"
  "Slack token|xox[baprs]-[0-9a-zA-Z-]+"
  "Google API key|AIza[0-9A-Za-z\-_]{35}"
  "PEM private key|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"
  "Generic high-entropy assignment|(?i)(secret|password|passwd|api_key|apikey|auth_token)\s*=\s*['\"][^'\"]{8,}"
)

for entry in "${PATTERNS[@]}"; do
  LABEL="${entry%%|*}"
  REGEX="${entry##*|}"
  if grep -qEi "$REGEX" "$FILE" 2>/dev/null; then
    echo "[secrets-scan] Possible secret in $FILE — $LABEL"
    FOUND=true
  fi
done

if [[ "$FOUND" == true ]]; then
  echo "[secrets-scan] Remove secrets before committing. Use environment variables or a secrets manager instead."
  exit 2
fi

exit 0

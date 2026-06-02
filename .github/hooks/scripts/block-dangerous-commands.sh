#!/usr/bin/env bash
# block-dangerous-commands.sh — Intercepts destructive shell operations before execution.
# Triggered by: PreToolUse
# Exit behaviour:
#   0  — allowed (or not a shell command tool)
#   0  + JSON stdout with permissionDecision:ask — requires user confirmation
#   2  + JSON stdout with permissionDecision:deny — hard block

set -euo pipefail

INPUT=$(cat)
TOOL=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('tool_name') or '')
" 2>/dev/null || echo "")

# Only intercept shell execution tools.
[[ "$TOOL" != "run_in_terminal" && "$TOOL" != "execute" && "$TOOL" != "terminal" ]] && exit 0

CMD=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input') or {}
print(ti.get('command') or ti.get('cmd') or '')
" 2>/dev/null || echo "")

[[ -z "$CMD" ]] && exit 0

# ── Hard block — immediately destructive, no exceptions ───────────────────────
declare -a BLOCKED=(
  "rm -rf /"
  "rm -rf ~"
  "rm -rf \$HOME"
  "git push --force-with-lease --force"
  "> /dev/sda"
  "dd if=/dev/zero"
  "mkfs"
  ":(){ :|:& };:"   # fork bomb
)

for pattern in "${BLOCKED[@]}"; do
  if echo "$CMD" | grep -qF "$pattern"; then
    python3 -c "
import json
print(json.dumps({
  'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'deny',
    'permissionDecisionReason': 'Hard-blocked: \"$pattern\" is irreversibly destructive. Run this manually if intentional.'
  }
}))
"
    exit 2
  fi
done

# ── Soft warn — affects shared state or is hard to reverse ────────────────────
declare -a WARN=(
  "git push --force"
  "git push -f "
  "git reset --hard"
  "git rebase"
  "git commit --amend"
  "npm publish"
  "npx prisma migrate reset"
  "npx prisma db push --force-reset"
  "DROP TABLE"
  "DROP DATABASE"
  "TRUNCATE"
)

for pattern in "${WARN[@]}"; do
  if echo "$CMD" | grep -qi "$pattern"; then
    python3 -c "
import json
print(json.dumps({
  'hookSpecificOutput': {
    'hookEventName': 'PreToolUse',
    'permissionDecision': 'ask',
    'permissionDecisionReason': 'Confirm: \"$pattern\" affects shared state or is hard to reverse. Proceed intentionally?'
  }
}))
"
    exit 0
  fi
done

exit 0

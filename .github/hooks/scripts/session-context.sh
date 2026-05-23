#!/usr/bin/env bash
# session-context.sh — Injects project context at the start of each agent session.
# Triggered by: SessionStart
# Output: JSON systemMessage with branch, last commit, detected stack, and open tasks.

set -euo pipefail

LINES=()

# ── Git context ───────────────────────────────────────────────────────────────
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "detached HEAD")
  COMMIT=$(git log -1 --oneline 2>/dev/null || echo "no commits yet")
  DIRTY=$(git diff --stat 2>/dev/null | tail -1 || echo "")

  LINES+=("**Branch**: \`$BRANCH\`")
  LINES+=("**Last commit**: $COMMIT")
  [[ -n "$DIRTY" ]] && LINES+=("**Uncommitted changes**: $DIRTY")
fi

# ── Stack detection ───────────────────────────────────────────────────────────
STACK=()

if [[ -f "package.json" ]]; then
  PKG_NAME=$(python3 -c "import json; d=json.load(open('package.json')); print(d.get('name',''))" 2>/dev/null || echo "")
  [[ -n "$PKG_NAME" ]] && STACK+=("Node ($PKG_NAME)")
  grep -q '"next"' package.json    2>/dev/null && STACK+=("Next.js")
  grep -q '"react"' package.json   2>/dev/null && STACK+=("React")
  grep -q '"vue"' package.json     2>/dev/null && STACK+=("Vue")
  grep -q '"svelte"' package.json  2>/dev/null && STACK+=("Svelte")
  grep -q '"express"' package.json 2>/dev/null && STACK+=("Express")
  grep -q '"fastify"' package.json 2>/dev/null && STACK+=("Fastify")
fi

[[ -f "pyproject.toml" || -f "requirements.txt" ]] && STACK+=("Python")
[[ -f "go.mod" ]]    && STACK+=("Go")
[[ -f "Gemfile" ]]   && STACK+=("Ruby")
[[ -f "Cargo.toml" ]] && STACK+=("Rust")

if [[ ${#STACK[@]} -gt 0 ]]; then
  STACK_STR=$(printf ", %s" "${STACK[@]}")
  LINES+=("**Stack**: ${STACK_STR:2}")
fi

# ── Agent system note ─────────────────────────────────────────────────────────
LINES+=("")
LINES+=("**Agents available**: Orchestrator · Planner · Coder · Designer")
LINES+=("**Skills available**: \`lint-and-analyse\` · \`ui-inspect\` · \`task-board\`")
LINES+=("**Hooks active**: format-on-save · lint-on-change · vulnerability-check · scan-secrets · block-dangerous-commands")

# ── Assemble JSON output ──────────────────────────────────────────────────────
MSG="## Session Context\\n\\n$(printf "%s\\n" "${LINES[@]}")"

python3 -c "
import json, sys
print(json.dumps({'systemMessage': sys.argv[1]}))
" "$MSG"

exit 0

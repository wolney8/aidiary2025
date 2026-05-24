#!/usr/bin/env bash
# context-snapshot.sh — Injects a system message before context compaction, prompting
# the agent to persist a summary of current work to session memory.
# Triggered by: PreCompact

set -euo pipefail

python3 -c "
import json
msg = (
    'CONTEXT COMPACTION IMMINENT\n\n'
    'Before this context is compacted, use the memory tool to write a snapshot to '
    '/memories/session/snapshot.md. Include:\n\n'
    '1. The task currently in progress (one sentence)\n'
    '2. What has been completed so far (bullet list)\n'
    '3. Remaining steps (bullet list)\n'
    '4. Any blocking issues or open questions\n\n'
    'Keep it under 20 lines. This snapshot will be read at the start of the next turn '
    'to restore context after compaction.'
)
print(json.dumps({'systemMessage': msg}))
"

exit 0

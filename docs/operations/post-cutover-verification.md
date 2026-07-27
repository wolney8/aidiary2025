# Post-Cutover Verification And Performance Baseline

## Purpose

Run this immediately after switching AI Diary to the cloud database. The goal is to prove
data correctness, catch regressions quickly, and record a baseline for future performance
comparisons.

## First 30 Minutes

1. Confirm `/health` returns `200`.
2. Log in with a known account.
3. Confirm entry counts match the migration report.
4. Open Entries in Cards and Calendar modes.
5. Open at least one Daily entry, Dream entry, Thought Record, Important Day, attachment,
   and reflection summary.
6. Confirm images and attachments resolve from storage keys.
7. Run an export package and confirm it completes.
8. Send one chat message and confirm the response persists in chat history.
9. Run the baseline capture command and save the JSON outside the repo.
10. Decide accept/rollback inside the cutover window.

## Baseline Command

Public-only check:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/capture_post_cutover_baseline.py \
  --base-url http://localhost:5001 \
  --samples 3 \
  --output-json /tmp/aidiary-post-cutover-baseline.json
```

Authenticated check:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/capture_post_cutover_baseline.py \
  --base-url http://localhost:5001 \
  --token "$JWT_ACCESS_TOKEN" \
  --samples 3 \
  --output-json /tmp/aidiary-post-cutover-baseline.json
```

The authenticated check samples:

- profile
- Daily entries
- Dream entries
- Important Days
- import history
- reflection summaries
- Thought Records
- On This Day
- chat observability report

## Data Integrity Checks

Compare post-cutover data against the migration evidence packet:

- total migrated rows
- user count
- Daily entry count
- Dream entry count
- attachment count
- important day count
- thought record count
- import history count
- reflection summary count
- chat message count

Any mismatch is a rollback trigger unless explained by known writes after the freeze ended.

## Performance Baseline

Capture:

- endpoint status codes
- average latency
- p95 latency
- error count
- sample count
- response shape and collection counts for successful JSON responses, without storing
  full response bodies

Store the JSON report outside the repo. If latency is materially worse than the SQLite
baseline or any sampled API endpoint returns `4xx`/`5xx`, roll back before accepting the
cutover.

## Go/No-Go

Accept the cutover only when:

- no data count mismatches are present
- no critical manual smoke path fails
- baseline capture has zero API errors
- media and attachment links work
- chat observability shows completed events after a test message

Rollback follows `cloud-cutover-runbook.md`.

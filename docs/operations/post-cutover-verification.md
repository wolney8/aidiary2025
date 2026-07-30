# Post-Cutover Verification And Performance Baseline

## Purpose

Run this immediately after switching AI Diary to the cloud database. The goal is to prove
data correctness, catch regressions quickly, and record a baseline for future performance
comparisons.

## First 30 Minutes

1. Confirm `/health` returns `200`.
2. Confirm `/api/health/database` returns `200` with `ok: true`.
3. Log in with a known account.
4. Confirm entry counts match the migration report.
5. Open Entries in Cards and Calendar modes.
6. Open at least one Daily entry, Dream entry, Thought Record, Important Day, attachment,
   and reflection summary.
7. Confirm images and attachments resolve from storage keys.
8. Run an export package and confirm it completes.
9. Send one chat message and confirm the response persists in chat history.
10. Run a Postgres snapshot export and save it outside the repo.
11. Run the baseline capture command and save the JSON outside the repo.
12. Decide accept/rollback inside the cutover window.

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

## Postgres Snapshot Command

```bash
cd server
source venv/bin/activate
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/export_postgres_snapshot.py \
  --output-dir ~/AIDiaryBackups/postgres-snapshots \
  --label post-cutover
```

Then validate the snapshot manifest and schema load plan:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir ~/AIDiaryBackups/postgres-snapshots/<snapshot-directory>
```

Optional local fallback rehearsal from that snapshot:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/restore_sqlite_from_snapshot.py \
  --export-dir ~/AIDiaryBackups/postgres-snapshots/<snapshot-directory> \
  --schema-db db/app.db \
  --target-db ~/AIDiaryBackups/restored-sqlite/post-cutover-rehearsal.db \
  --overwrite
```

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

- app health and database health both pass
- a post-cutover Postgres snapshot exists and its manifest validates
- optional but recommended: the snapshot restores into a local SQLite rehearsal DB
- no data count mismatches are present
- no critical manual smoke path fails
- baseline capture has zero API errors
- media and attachment links work
- chat observability shows completed events after a test message

Rollback follows `cloud-cutover-runbook.md`.

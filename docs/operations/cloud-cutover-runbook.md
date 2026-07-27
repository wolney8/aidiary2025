# Cloud Database Cutover Runbook

## Purpose

This runbook defines the operational sequence for moving AI Diary from SQLite to managed
Postgres after `cloud-cutover-checklist.md` passes. It is intentionally conservative:
cutover is a configuration switch only after migration tooling, parity checks, and
rollback rehearsal have completed.

## Roles

- Cutover lead: coordinates timing, checklist evidence, and final go/no-go.
- Backend operator: runs backup, migration export/load, backend tests, and config switch.
- Frontend operator: runs frontend checks and browser smoke.
- Rollback owner: executes rollback if any trigger is hit.
- Recorder: captures command outputs, timings, and decisions.

For a solo/local deployment, one person may hold multiple roles, but each role should be
explicitly assigned before the cutover window starts.

## Freeze Criteria

Start the write freeze only when all are true:

- `main` is clean and pushed.
- No feature branches are waiting to be merged into the cutover candidate.
- SQLite backup path is known and outside the repo.
- `DATABASE_URL` points to the intended Postgres rehearsal or production target.
- `cloud-cutover-checklist.md` pre-cutover gates have passed.
- The rollback owner has confirmed the rollback command path.

During freeze:

- do not create, import, edit, or delete entries
- do not upload attachments/images
- do not run background imports
- do not change Personalisation/Customisation settings

## Rehearsal Evidence Packet

Before production cutover, capture these artifacts:

- SQLite backup filename and timestamp.
- Migration audit JSON path.
- JSONL export directory path.
- Postgres target identifier or Neon branch name.
- Output of `load_cloud_migration.py --apply`.
- Output of `audit_runtime_sqlite_usage.py`.
- Output of `validate_cloud_cutover_readiness.py`.
- Backend test output.
- Frontend lint/build output.
- Manual parity smoke notes.
- Rollback rehearsal notes.

Keep this packet outside the repository unless sanitised.

## Timing Plan

Recommended cutover window for the current app size:

- T-30 min: confirm no active local writes and create SQLite backup.
- T-25 min: run migration audit/export from the backed-up SQLite source.
- T-20 min: run Postgres load into target database.
- T-15 min: run readiness validator and backend smoke.
- T-10 min: switch backend configuration to `DATABASE_URL`.
- T-5 min: restart backend and verify health.
- T+0: start manual parity smoke.
- T+15 min: decide accept or rollback.

Adjust timings after the first real Neon branch rehearsal.

## Execution Steps

1. Announce freeze.
2. Stop or avoid local write activity.
3. Create SQLite backup.
4. Run audit/export:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/rehearse_cloud_migration.py \
  --source-db db/app.db \
  --export-dir /tmp/aidiary-cloud-export \
  --report-json /tmp/aidiary-cloud-migration-report.json
```

5. Run loader dry-run:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export
```

6. Apply to Postgres target:

```bash
cd server
source venv/bin/activate
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-cloud-export \
  --apply \
  --reset-first
```

7. Run runtime SQLite usage audit:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/audit_runtime_sqlite_usage.py --repo-root ..
```

8. Run readiness validator with evidence flags.
9. Switch backend database configuration.
10. Restart backend.
11. Run health check and manual parity smoke.
12. Create the cutover evidence packet.
13. Accept cutover only if no rollback trigger is hit.

Evidence packet command:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_cutover_evidence_packet.py \
  --sqlite-backup /tmp/aidiary-sqlite-backup.db \
  --export-dir /tmp/aidiary-cloud-export \
  --migration-report /tmp/aidiary-cloud-migration-report.json \
  --readiness-report /tmp/aidiary-cloud-readiness.json \
  --preflight-report /tmp/aidiary-production-preflight.json \
  --post-cutover-baseline /tmp/aidiary-post-cutover-baseline.json \
  --postgres-target "neon/rehearsal-branch-or-production-db" \
  --backend-tests-passed \
  --frontend-lint-passed \
  --frontend-build-passed \
  --manual-smoke-passed \
  --rollback-rehearsed \
  --output-json /tmp/aidiary-cutover-evidence-packet.json
```

## Rollback Rehearsal Scenarios

Run these against a rehearsal branch before production:

- Failed Postgres load:
  - simulate by using a malformed or incomplete export directory
  - expected result: loader fails, SQLite source remains untouched
- Failed readiness validation:
  - omit `--postgres-rehearsal-loaded`
  - expected result: validator returns non-zero and blocks cutover
- Failed app smoke after config switch:
  - point backend back to SQLite `DB_PATH`
  - expected result: login and entry list work from SQLite again
- Media reference regression:
  - verify image and attachment storage keys still resolve after rollback

## Rollback Steps

1. Stop writes immediately.
2. Restore previous backend config:
   - remove or disable `DATABASE_URL`
   - restore `DB_PATH` to the SQLite source or backup
3. Restart backend.
4. Verify:
   - `/health`
   - login
   - entries list
   - calendar
   - package export
5. Record failure details and preserve the failed Postgres database for comparison.

## Escalation

Escalate rather than proceeding if:

- source and export row counts differ
- any orphan rows are found
- media reference checks are non-zero
- runtime SQLite usage audit reports route/service violations
- backend tests fail
- frontend build fails
- rollback path has not been rehearsed
- Postgres provider status is degraded

## Acceptance

`#73` is complete when:

- this runbook is reviewed
- one disposable Postgres rehearsal has been run
- at least one rollback scenario has been rehearsed
- the evidence packet exists
- the cutover lead records a go/no-go decision

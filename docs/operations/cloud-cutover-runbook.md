# Cloud Database Cutover Runbook

## Purpose

This runbook defines the operational sequence for moving OpenMynd from SQLite to managed
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
- The newest SQLite backup manifest has been reviewed for expected table counts.
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
- Rollback rehearsal JSON report.

Keep this packet outside the repository unless sanitised.

## Timing Plan

Recommended cutover window for the current app size:

- T-30 min: confirm no active local writes and create SQLite backup.
- T-25 min: run migration audit/export from the backed-up SQLite source.
- T-20 min: run Postgres load into target database.
- T-15 min: run readiness validator and backend smoke.
- T-10 min: switch backend configuration to `DATABASE_URL`.
- T-5 min: restart backend and verify app plus database health.
- T+0: start manual parity smoke.
- T+15 min: decide accept or rollback.

Adjust timings after the first real Neon branch rehearsal.

## Execution Steps

1. Announce freeze.
2. Stop or avoid local write activity.
3. Create SQLite backup:

Shortcut for a local-only rehearsal package:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/run_neon_cutover_rehearsal.py \
  --source-db db/app.db \
  --work-dir ~/OpenMyndBackups/neon-rehearsals/manual
```

Shortcut to apply the backed-up/exported data to an approved Neon rehearsal target:

```bash
cd server
source venv/bin/activate
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/run_neon_cutover_rehearsal.py \
  --source-db db/app.db \
  --work-dir ~/OpenMyndBackups/neon-rehearsals/manual \
  --apply
```

Use `--reset-first --confirm-reset RESET_NON_EMPTY_POSTGRES` only for a disposable
rehearsal database or an explicitly approved reset.

Manual step-by-step commands are retained below for evidence gathering and debugging.

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_sqlite_backup.py \
  --source-db db/app.db \
  --backup-dir ~/OpenMyndBackups \
  --label pre-cutover \
  --retain 14
```

4. Run audit/export:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/rehearse_cloud_migration.py \
  --source-db db/app.db \
  --export-dir /tmp/openmynd-cloud-export \
  --report-json /tmp/openmynd-cloud-migration-report.json
```

5. Run loader dry-run:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/openmynd-cloud-export
```

6. Apply to Postgres target:

```bash
cd server
source venv/bin/activate
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/openmynd-cloud-export \
  --apply \
  --reset-first \
  --confirm-reset RESET_NON_EMPTY_POSTGRES
```

The reset confirmation is required only when the target already contains OpenMynd
managed rows. Do not use it against a production database unless the reset is part of
an approved cutover or rollback procedure.

7. Run runtime SQLite usage audit:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/audit_runtime_sqlite_usage.py --repo-root ..
```

8. Run readiness validator with evidence flags.
9. Switch backend database configuration.
   - public production target: `APP_ENV=production`, `DATABASE_PROVIDER=postgres`,
     `DATABASE_URL`, explicit `MEDIA_ROOT` or media backend config, and shared
     `RATELIMIT_STORAGE_URI`
   - do not set `OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK` during normal cutover
10. Restart backend.
11. Run app health, database health, and manual parity smoke.
12. Create the cutover evidence packet.
13. Accept cutover only if no rollback trigger is hit.

Health checks after restart:

```bash
curl -f http://localhost:5001/health
curl -f http://localhost:5001/api/health/database
```

The first check proves the Flask app is serving. The second proves the configured
database provider can accept a query. Both must pass before manual parity smoke starts.

Evidence packet command:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_cutover_evidence_packet.py \
  --sqlite-backup /tmp/openmynd-sqlite-backup.db \
  --export-dir /tmp/openmynd-cloud-export \
  --migration-report /tmp/openmynd-cloud-migration-report.json \
  --readiness-report /tmp/openmynd-cloud-readiness.json \
  --preflight-report /tmp/openmynd-production-preflight.json \
  --post-cutover-baseline /tmp/openmynd-post-cutover-baseline.json \
  --rollback-report /tmp/openmynd-rollback-rehearsal.json \
  --postgres-target "neon/rehearsal-branch-or-production-db" \
  --backend-tests-passed \
  --frontend-lint-passed \
  --frontend-build-passed \
  --manual-smoke-passed \
  --rollback-rehearsed \
  --output-json /tmp/openmynd-cutover-evidence-packet.json
```

Rehearsal sign-off command:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_cutover_rehearsal_signoff.py \
  --evidence-packet /tmp/openmynd-cutover-evidence-packet.json \
  --cutover-lead "Will" \
  --backend-operator "Will" \
  --frontend-operator "Will" \
  --rollback-owner "Will" \
  --recorder "Will" \
  --freeze-started-at "2026-07-27T10:00:00Z" \
  --migration-started-at "2026-07-27T10:05:00Z" \
  --config-switched-at "2026-07-27T10:20:00Z" \
  --decision-due-at "2026-07-27T10:35:00Z" \
  --decision go \
  --notes "Disposable branch rehearsal completed without rollback triggers." \
  --output-json /tmp/openmynd-cutover-rehearsal-signoff.json
```

This report is the final dry-run artifact. It should fail if the evidence packet is
incomplete, rollback evidence failed, owners are unassigned, timing markers are missing,
or the explicit decision is `no-go`.

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

Capture the rollback rehearsal result as structured evidence after restoring SQLite
configuration and running the rollback baseline/smoke:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_rollback_rehearsal_report.py \
  --scenario "failed app smoke after config switch" \
  --sqlite-backup /tmp/openmynd-sqlite-backup.db \
  --rollback-baseline /tmp/openmynd-rollback-baseline.json \
  --postgres-target "neon/rehearsal-branch" \
  --failure-summary "Backend was pointed back to SQLite after a failed smoke rehearsal." \
  --config-restored \
  --health-passed \
  --auth-smoke-passed \
  --entries-smoke-passed \
  --export-smoke-passed \
  --media-smoke-passed \
  --output-json /tmp/openmynd-rollback-rehearsal.json
```

## Rollback Steps

1. Stop writes immediately.
2. Restore previous backend config:
   - remove or disable `DATABASE_URL`
   - restore `DB_PATH` to the SQLite source or backup
   - if `APP_ENV=production`, set `OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK=true`
     and `OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION=true` only for the rollback
     window
3. Restart backend.
4. Verify:
   - `/health`
   - `/api/health/database`
   - login
   - entries list
   - calendar
   - package export
5. Record failure details and preserve the failed Postgres database for comparison.

Use [local-sqlite-backup-and-fallback.md](./local-sqlite-backup-and-fallback.md) for
the exact local fallback process if Neon or another provider becomes unavailable before
cutover acceptance.

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

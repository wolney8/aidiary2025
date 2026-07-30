# Local SQLite Backup And Fallback

## Purpose

Use this process while AI Diary is still SQLite-first or during a controlled cloud
cutover rehearsal. The goal is to preserve a restorable local database if Neon or
another managed Postgres provider becomes unavailable.

Backups can contain real diary content, test entries, imported data, attachment
metadata, and AI outputs. Keep them outside the repository and outside public artifact
folders.

## Create A Backup

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/create_sqlite_backup.py \
  --source-db db/app.db \
  --backup-dir ~/AIDiaryBackups \
  --label pre-cutover \
  --retain 14
```

The command writes:

- `aidiary-sqlite-<timestamp>-<label>.db`
- `aidiary-sqlite-<timestamp>-<label>.manifest.json`

The manifest records only operational metadata: backup path, byte size, checksum, table
counts, total rows, and retention actions. It does not export row contents.

## Suggested Automatic Backup

For local development before cloud cutover, run a scheduled SQLite backup outside the
repo. A simple daily cron entry is enough until a hosted scheduler exists:

```cron
15 20 * * * cd /Users/will_work/Scripts/PythonScripts/aidiary2025/aidiary2025/server && /bin/zsh -lc 'source venv/bin/activate && PYTHONPATH=. python scripts/create_sqlite_backup.py --source-db db/app.db --backup-dir ~/AIDiaryBackups --label daily --retain 14 >/tmp/aidiary-sqlite-backup.log 2>&1'
```

Use `launchd` instead of cron on macOS if you want richer logs and startup behaviour.
The important constraint is the same: write backups outside the repository.

## Postgres Snapshot After Cutover

After cloud cutover is accepted, local SQLite backups no longer capture new cloud writes.
Use a scheduled Postgres snapshot export instead:

```bash
cd server
source venv/bin/activate
DATABASE_URL="postgresql://..." PYTHONPATH=. python scripts/export_postgres_snapshot.py \
  --output-dir ~/AIDiaryBackups/postgres-snapshots \
  --label scheduled
```

The snapshot uses the same JSONL plus `manifest.json` shape as the migration rehearsal
export. It is provider-portable and can be validated with the existing cloud load-plan
checks:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir ~/AIDiaryBackups/postgres-snapshots/<snapshot-directory>
```

This gives us durable local evidence of the cloud data even if a managed provider account
or branch becomes unavailable later. Rebuilding a runnable local SQLite database directly
from a Postgres snapshot remains a separate restore-tooling issue.

## Local Fallback If Neon Access Is Lost

If Neon is unavailable before the cloud cutover is accepted:

1. Stop writes immediately.
2. Pick the newest known-good SQLite backup.
3. Copy it to the intended local runtime path, for example:

```bash
cp ~/AIDiaryBackups/aidiary-sqlite-YYYYMMDDTHHMMSSZ-pre-cutover.db server/db/app.db
```

4. Start the backend with local SQLite configuration:

```bash
DATABASE_PROVIDER=sqlite
DB_PATH=server/db/app.db
DATABASE_URL=
```

5. Restart the backend.
6. Verify:

```bash
curl -f http://localhost:5001/health
curl -f http://localhost:5001/api/health/database
```

7. Run the local smoke paths: login, entries list, calendar, create/edit entry, images,
   attachments, import history, and export package.

## Split-Brain Rule

Do not treat an old SQLite backup as an automatic replacement for a Postgres database
after users have written new data to Postgres. That would lose cloud-only writes.

After a real cloud cutover is accepted, runnable local fallback requires a separate
Postgres-to-SQLite restore process or a full offline-sync architecture. Until that
exists, SQLite fallback is a rollback tool for rehearsals and pre-acceptance cutover
windows, while Postgres snapshots are the local safety record for cloud-era data.

## Test Data And Real Data

The current local database may contain both real personal entries and imported/test
entries. Backups preserve both. Before a public or production cloud migration, decide
whether to:

- migrate the full current database as-is
- delete test/import trial data first using the app's bulk-delete tools
- rehearse with the mixed database, then cut over using a cleaned final export

Do not manually edit the database to remove test rows unless there is a separate audited
cleanup script and a fresh backup.

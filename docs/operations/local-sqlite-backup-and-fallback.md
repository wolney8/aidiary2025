# Local SQLite Backup And Fallback

## Purpose

Use this process while OpenMynd is still SQLite-first or during a controlled cloud
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
  --backup-dir ~/OpenMyndBackups \
  --label pre-cutover \
  --retain 14
```

The command writes:

- `openmynd-sqlite-<timestamp>-<label>.db`
- `openmynd-sqlite-<timestamp>-<label>.manifest.json`

The manifest records only operational metadata: backup path, byte size, checksum, table
counts, total rows, and retention actions. It does not export row contents.

## Suggested Automatic Backup

For local development before cloud cutover, run a scheduled SQLite backup outside the
repo. A simple daily cron entry is enough until a hosted scheduler exists:

```cron
15 20 * * * cd /Users/will_work/Scripts/PythonScripts/openmynd/server && /bin/zsh -lc 'source venv/bin/activate && PYTHONPATH=. python scripts/create_sqlite_backup.py --source-db db/app.db --backup-dir ~/OpenMyndBackups --label daily --retain 14 >/tmp/openmynd-sqlite-backup.log 2>&1'
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
  --output-dir ~/OpenMyndBackups/postgres-snapshots \
  --label scheduled
```

The snapshot uses the same JSONL plus `manifest.json` shape as the migration rehearsal
export. It is provider-portable and can be validated with the existing cloud load-plan
checks:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir ~/OpenMyndBackups/postgres-snapshots/<snapshot-directory>
```

This gives us durable local evidence of the cloud data even if a managed provider account
or branch becomes unavailable later.

## Restore A Runnable Local SQLite Database From A Snapshot

Use this only with a validated snapshot and a known-good SQLite schema template:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/restore_sqlite_from_snapshot.py \
  --export-dir ~/OpenMyndBackups/postgres-snapshots/<snapshot-directory> \
  --schema-db db/app.db \
  --target-db ~/OpenMyndBackups/restored-sqlite/app-restored.db
```

The command refuses to overwrite an existing target unless `--overwrite` is supplied. It
copies the schema from `--schema-db`, clears managed app tables, validates the snapshot
manifest, loads rows in dependency order, and runs `PRAGMA foreign_key_check`.

For a local fallback run, point the backend at the restored database:

```bash
DATABASE_PROVIDER=sqlite
DB_PATH=~/OpenMyndBackups/restored-sqlite/app-restored.db
DATABASE_URL=
OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK=true
OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION=true
```

## Local Fallback If Neon Access Is Lost

If Neon is unavailable before the cloud cutover is accepted:

1. Stop writes immediately.
2. Pick the newest known-good SQLite backup.
3. Copy it to the intended local runtime path, for example:

```bash
cp ~/OpenMyndBackups/openmynd-sqlite-YYYYMMDDTHHMMSSZ-pre-cutover.db server/db/app.db
```

4. Start the backend with local SQLite configuration:

```bash
DATABASE_PROVIDER=sqlite
DB_PATH=server/db/app.db
DATABASE_URL=
OPENMYND_ALLOW_SQLITE_PRODUCTION_FALLBACK=true
OPENMYND_ALLOW_RUNTIME_MIGRATIONS_IN_PRODUCTION=true
```

5. If `APP_ENV=production`, set the two `OPENMYND_ALLOW_*` flags only for the rollback
   window and record why the fallback is active.
6. Restart the backend.
7. Verify:

```bash
curl -f http://localhost:5001/health
curl -f http://localhost:5001/api/health/database
```

8. Run the local smoke paths: login, entries list, calendar, create/edit entry, images,
   attachments, import history, and export package.

## Split-Brain Rule

Do not treat an old SQLite backup as an automatic replacement for a Postgres database
after users have written new data to Postgres. That would lose cloud-only writes.

After a real cloud cutover is accepted, runnable local fallback should use the latest
validated Postgres snapshot plus `restore_sqlite_from_snapshot.py`. This is still an
operator-controlled recovery process, not automatic multi-device offline sync.

## Test Data And Real Data

The current local database may contain both real personal entries and imported/test
entries. Backups preserve both. Before a public or production cloud migration, decide
whether to:

- migrate the full current database as-is
- delete test/import trial data first using the app's bulk-delete tools
- rehearse with the mixed database, then cut over using a cleaned final export

Do not manually edit the database to remove test rows unless there is a separate audited
cleanup script and a fresh backup.

# Cloud Database Provider Options

Updated: 29 July 2026

## Decision Context

AWS is currently blocked by account/customer-service issues, so the cloud database path
must stay provider-flexible and avoid AWS-specific assumptions.

The application already supports the correct portability seam:

- local development: `DATABASE_PROVIDER=sqlite` plus `DB_PATH`
- managed database rehearsal/production: `DATABASE_PROVIDER=postgres` plus
  `DATABASE_URL`

Do not add provider SDKs or provider-specific database code for the initial migration.
Use standard Postgres connections through `DATABASE_URL`.

## Recommended Provider Order

### 1. Neon Postgres

Best first choice for migration rehearsal.

Why:

- free plan is available
- standard Postgres connection string
- branching is well suited to disposable migration rehearsals
- aligns with the existing ADR and cutover docs

Risk:

- free-tier limits can change
- production usage may move to paid usage-based pricing

### 2. Supabase Postgres

Best fallback if Neon account/setup becomes blocked.

Why:

- free plan is available
- standard Postgres access
- includes Auth and Storage if the app later chooses a broader platform direction

Risk:

- adopting Supabase Auth/Storage too early would create product architecture coupling
- use only its Postgres connection for this migration unless a later ADR says otherwise

### 3. Render Postgres

Good for app-hosting alignment, but less ideal as the free database target.

Why:

- simple platform if the backend/frontend are also hosted on Render
- standard Postgres

Risk:

- Render free Postgres is documented as preview/hobby-style and not production-suitable
- current docs describe free instances as limited and not for production use

### 4. Railway Postgres

Useful developer fallback, not the preferred durable target.

Why:

- quick to create Postgres-backed projects
- standard connection model

Risk:

- free/trial/credit model is less predictable for long-running database rehearsal
- usage-based billing can surprise if left running

## Practical Recommendation

Use this order:

1. Try Neon free branch/project for `#28` disposable rehearsal.
2. If Neon setup blocks, use Supabase free Postgres for the same `DATABASE_URL` flow.
3. Use Render or Railway only if they are already hosting the app runtime or if Neon and
   Supabase both block.

## Required Rehearsal Environment

```bash
DATABASE_PROVIDER=postgres
DATABASE_URL="postgresql://..."
DATABASE_USES_POOLER=true
```

For the first disposable rehearsal, run:

```bash
cd server
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python scripts/run_postgres_migrations.py --apply
PYTHONPATH=. python scripts/load_cloud_migration.py \
  --export-dir /tmp/aidiary-local-cutover-rehearsal/export \
  --apply \
  --reset-first
```

Use `--reset-first` only on a throwaway rehearsal database or branch.

## Failure Visibility

The backend exposes a provider-neutral health endpoint:

```bash
curl http://localhost:5001/api/health/database
```

Expected healthy response shape:

```json
{
  "provider": "postgres",
  "ok": true,
  "latency_ms": 42.0
}
```

If the managed database is unavailable, full, paused, misconfigured, or rejecting
connections, the endpoint returns `503` with sanitized failure metadata. It does not
expose database URLs, credentials, hosts, or row data.

This is server-side detection only. The app does not yet have offline-first local draft
sync for a cloud outage. If Neon or another provider rejects writes, the backend should
return an error and the frontend should surface it; durable offline queueing for user
entries is a separate product issue because it changes conflict resolution, device
storage, and account-sync semantics.

## Owner Decision Needed

Choose one provider account for the first disposable rehearsal:

- Neon first
- Supabase fallback
- Render/Railway only if preferred for hosting alignment

Once a `DATABASE_URL` exists, `#28` can proceed without code changes.

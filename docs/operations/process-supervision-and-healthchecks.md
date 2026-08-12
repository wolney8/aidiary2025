# Process Supervision And Healthchecks

Updated: 12 August 2026

Scope: production/runtime restart behavior for the OpenMynd API.

This file is public-safe. Do not add real hostnames, credentials, database URLs, or
incident notes.

## Principle

The Flask app should fail loudly when its process cannot run safely. Automatic restart
belongs to the hosting platform or process supervisor:

- Render/Railway/Fly-style managed services: configure the service start command and
  healthcheck URL so the platform restarts failed instances.
- VPS/systemd: use the checked-in `deploy/systemd/openmynd-api.service.example` with
  `Restart=on-failure`.
- Local development: restart manually or use the Angular/Flask dev servers directly; do
  not treat the Flask dev server as production supervision.

## Production Start Command

Use Gunicorn through the committed config:

```bash
cd server
gunicorn -c gunicorn.conf.py wsgi:app
```

Default behavior:

- binds to `0.0.0.0:${PORT:-5001}`
- logs to stdout/stderr for platform collection
- uses multiple workers and threads
- recycles workers with jitter to reduce memory-leak risk
- supports environment overrides such as `WEB_CONCURRENCY`, `GUNICORN_THREADS`, and
  `GUNICORN_TIMEOUT`

## Healthcheck Command

The dependency-free healthcheck verifies both the process and the configured database:

```bash
cd server
source venv/bin/activate
PYTHONPATH=. python scripts/healthcheck.py --base-url http://127.0.0.1:5001
```

For deployment or cutover checks, include a temporary database write probe:

```bash
PYTHONPATH=. python scripts/healthcheck.py \
  --base-url https://api.openmynd.example \
  --database-write
```

The script exits `0` when every check is healthy and non-zero when any check fails.

## Managed Hosting Settings

For a managed web service, configure:

- start command: `gunicorn -c gunicorn.conf.py wsgi:app`
- healthcheck path: `/health`
- readiness/deeper healthcheck path where supported: `/api/health/database`
- restart policy: platform default automatic restart on crash
- deploy gate before startup:

```bash
APP_ENV=production PYTHONPATH=. python scripts/validate_production_preflight.py --require-postgres
PYTHONPATH=. python scripts/run_postgres_migrations.py --apply
```

## VPS/Systemd Outline

1. Create an unprivileged `openmynd` user.
2. Deploy the repo under `/opt/openmynd`.
3. Put secrets and runtime settings in `/etc/openmynd/openmynd-api.env`.
4. Copy `deploy/systemd/openmynd-api.service.example` to
   `/etc/systemd/system/openmynd-api.service`.
5. Run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openmynd-api
sudo systemctl status openmynd-api
```

Validate after startup:

```bash
curl -f http://127.0.0.1:5001/health
curl -f http://127.0.0.1:5001/api/health/database
```

## Boundaries

- This does not replace database backups, point-in-time recovery, or migration
  rehearsals.
- This does not make local SQLite safe for public multi-user production.
- This does not restart the Angular dev server in local development.
- If the app repeatedly crashes on startup, the supervisor should keep it down or mark it
  unhealthy rather than masking the fault indefinitely.


#!/usr/bin/env bash
set -euo pipefail

if [ "${DATABASE_PROVIDER:-sqlite}" = "postgres" ]; then
  echo "Applying pending Postgres migrations..."
  PYTHONPATH=. python scripts/run_postgres_migrations.py --apply
fi

exec gunicorn -c gunicorn.conf.py wsgi:app

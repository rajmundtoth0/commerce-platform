#!/usr/bin/env bash
# Container entrypoint. Subcommands keep one image usable for every role:
#   api      -> run the HTTP server (default)
#   migrate  -> apply Alembic migrations, then exit
#   rebuild  -> rebuild all Redis projections from Postgres, then exit
#   worker   -> placeholder for a future async consumer
set -euo pipefail

cmd="${1:-api}"

case "$cmd" in
  api)
    # Single worker per pod; scale with Kubernetes replicas, not uvicorn workers.
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  rebuild)
    exec commerce rebuild
    ;;
  *)
    # Fall through to an arbitrary command (e.g. `commerce list-projections`).
    exec "$@"
    ;;
esac

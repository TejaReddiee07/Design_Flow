#!/bin/sh
set -e
cd /app/backend

echo "[entrypoint] waiting for MongoDB..."
python scripts/wait_for_db.py

case "$1" in
  api)
    echo "[entrypoint] ensuring indexes + seeding (admin, services, agents)"
    python -m app.db.seed
    echo "[entrypoint] starting api"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"
    ;;
  worker)
    echo "[entrypoint] starting worker"
    exec python -m app.worker
    ;;
  seed|migrate)
    exec python -m app.db.seed
    ;;
  *)
    exec "$@"
    ;;
esac

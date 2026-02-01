#!/usr/bin/env bash
set -euo pipefail

echo "Running migrations..."
alembic upgrade head

echo "Seeding initial users (if empty)..."
python -c "from app.db.session import SessionLocal; from app.db.init_db import ensure_seeded; db=SessionLocal(); ensure_seeded(db); db.close()"

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

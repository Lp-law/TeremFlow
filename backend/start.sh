#!/usr/bin/env bash
set -euo pipefail

# Run from backend dir so Python finds the 'app' module (Render may run from repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH:-}"

# Render requires binding to PORT; default 8000 for local
export PORT="${PORT:-8000}"
echo "Starting API on 0.0.0.0:${PORT}"

echo "Running migrations..."
alembic upgrade head
REV=$(alembic current 2>/dev/null | awk '{print $1}' || echo "none")
echo "DB revision after migrate: ${REV}"

echo "Seeding initial users (if empty)..."
python -c "from app.db.session import SessionLocal; from app.db.init_db import ensure_seeded; db=SessionLocal(); ensure_seeded(db); db.close()"

echo "Binding to port ${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

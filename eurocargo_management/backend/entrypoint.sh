#!/bin/sh
set -e

echo "Running Alembic migrations..."
if python -m alembic upgrade head; then
    echo "Migrations applied successfully."
else
    echo "WARNING: Alembic migration failed. Starting the application anyway." >&2
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

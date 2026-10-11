#! /usr/bin/env bash

set -e
set -x

# SQLite uses SQLModel.metadata.create_all() during initial data setup.
# PostgreSQL keeps using Alembic migrations.
if [[ "${DATABASE_URL:-}" == sqlite* ]]; then
  echo "SQLite database detected; skipping Alembic migrations."
else
  alembic upgrade head
fi

# Create initial data in DB
python app/initial_data.py

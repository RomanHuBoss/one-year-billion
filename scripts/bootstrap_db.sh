#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
for migration in migrations/[0-9][0-9][0-9][0-9]_*.sql; do
  base="$(basename "$migration")"
  if [ "$base" = "0002_seed_demo.sql" ]; then
    continue
  fi
  echo "Applying $migration"
  psql "$DATABASE_URL" -f "$migration"
done
if [ "${CAS_SEED_DEMO_DATA:-false}" = "true" ]; then
  psql "$DATABASE_URL" -f migrations/0002_seed_demo.sql
else
  echo "Core migrations applied. Demo seed skipped; set CAS_SEED_DEMO_DATA=true only for local smoke/demo."
fi

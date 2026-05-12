#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
psql "$DATABASE_URL" -f migrations/0001_core_schema.sql
if [ "${CAS_SEED_DEMO_DATA:-false}" = "true" ]; then
  psql "$DATABASE_URL" -f migrations/0002_seed_demo.sql
else
  echo "Core schema applied. Demo seed skipped; set CAS_SEED_DEMO_DATA=true only for local smoke/demo."
fi

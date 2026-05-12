#!/usr/bin/env bash
set -euo pipefail
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
python scripts/validate_project.py
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

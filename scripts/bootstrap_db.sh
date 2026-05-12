#!/usr/bin/env bash
set -euo pipefail
# Совместимость со старыми инструкциями. Основная реализация теперь Python,
# чтобы этот же bootstrap безопасно запускался из операторского интерфейса.
args=()
if [ "${CAS_SEED_DEMO_DATA:-false}" = "true" ]; then
  args+=(--seed-demo)
fi
exec "${PYTHON:-python}" scripts/bootstrap_db.py "${args[@]}"

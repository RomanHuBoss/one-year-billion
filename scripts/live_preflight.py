#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.settings import Settings
from app.config.runtime import build_runtime_config
from app.live.preflight import run_live_preflight
from app.db.connection import Database
from app.db.repository import Repository


def main() -> int:
    settings = Settings()
    runtime = build_runtime_config()
    db = None
    repo = None
    db_available = False
    db_error = None
    if settings.require_db_for_live or settings.live_requested:
        try:
            db = Database(settings.database_url)
            db.open()
            db.fetch_one('SELECT 1 AS ok')
            repo = Repository(db)
            db_available = True
        except Exception as exc:
            db_error = f'{type(exc).__name__}:{exc}'
    result = run_live_preflight(settings, runtime, db_available=db_available, repository=repo)
    payload = {'status': result.status, 'reasons': result.reasons, 'checks': result.checks, 'data': result.data, 'db_error': db_error}
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    if db is not None:
        db.close()
    return 0 if result.ok else 2


if __name__ == '__main__':
    raise SystemExit(main())

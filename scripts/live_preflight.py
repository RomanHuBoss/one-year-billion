#!/usr/bin/env python3
from __future__ import annotations
import argparse
import contextlib
import io
import json
import os
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
    parser = argparse.ArgumentParser(description='Fail-closed preflight для testnet/live без отправки ордеров.')
    parser.add_argument('--mode', choices=['testnet', 'live'], default=None)
    args = parser.parse_args()
    if args.mode == 'testnet':
        os.environ.setdefault('BYBIT_TESTNET', 'true')
    elif args.mode == 'live':
        os.environ.setdefault('BYBIT_TESTNET', 'false')
        os.environ.setdefault('APP_ENV', 'prod')

    settings = Settings()
    runtime = build_runtime_config()
    db = None
    repo = None
    db_available = False
    db_error = None
    if settings.require_db_for_live or settings.live_requested:
        # psycopg_pool пишет retry diagnostics в stderr. Для CLI preflight это
        # не должно маскировать JSON-result; все детали остаются в db_error.
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                db = Database(settings.database_url)
                db.open()
                db.fetch_one('SELECT 1 AS ok')
                repo = Repository(db)
                db_available = True
            except Exception as exc:
                db_error = f'{type(exc).__name__}:{exc}'
    result = run_live_preflight(settings, runtime, db_available=db_available, repository=repo)
    payload = {'status': result.status, 'mode': args.mode or ('testnet' if settings.bybit_testnet else 'live'), 'reasons': result.reasons, 'checks': result.checks, 'data': result.data, 'db_error': db_error}
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    if db is not None:
        db.close()
    return 0 if result.ok else 2


if __name__ == '__main__':
    raise SystemExit(main())

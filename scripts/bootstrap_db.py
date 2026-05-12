#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.connection import Database


def _load_dotenv(path: Path = ROOT / '.env') -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _migration_files(seed_demo: bool) -> list[Path]:
    files: list[Path] = []
    for path in sorted((ROOT / 'migrations').glob('[0-9][0-9][0-9][0-9]_*.sql')):
        if path.name == '0002_seed_demo.sql' and not seed_demo:
            continue
        files.append(path)
    return files


def apply_migrations(database_url: str, seed_demo: bool = False) -> dict[str, Any]:
    db = Database(database_url)
    applied: list[str] = []
    db.open()
    try:
        db.fetch_one('SELECT 1 AS ok')
        for path in _migration_files(seed_demo):
            sql = path.read_text(encoding='utf-8')
            # SQL-файлы содержат собственные BEGIN/COMMIT и PL/pgSQL blocks.
            # Выполняем их как единый SQL-текст, без shell и без psql.
            db.execute(sql)
            applied.append(path.name)
    finally:
        db.close()
    return {
        'status': 'ok',
        'applied_migrations': applied,
        'seed_demo': seed_demo,
        'message': 'Миграции PostgreSQL применены через Python без shell/psql.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Применить PostgreSQL migrations через Python без bootstrap_db.sh/psql.')
    parser.add_argument('--seed-demo', action='store_true', help='Применить migrations/0002_seed_demo.sql. Только для локального smoke/demo.')
    args = parser.parse_args()
    _load_dotenv()
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print(json.dumps({'status': 'blocked', 'reasons': ['DATABASE_URL_required']}, ensure_ascii=False))
        return 2
    try:
        payload = apply_migrations(database_url=database_url, seed_demo=args.seed_demo)
    except Exception as exc:
        print(json.dumps({'status': 'blocked', 'reasons': [f'{type(exc).__name__}:{exc}']}, ensure_ascii=False, default=str))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config.runtime import build_runtime_config
from app.core.hashes import new_trace_id
from app.core.settings import Settings
from app.db.connection import Database
from app.db.repository import Repository


def main() -> int:
    parser = argparse.ArgumentParser(description='Record audited Go/No-Go evidence in PostgreSQL.')
    parser.add_argument('--type', required=True, choices=['PHASE0_PAPER', 'RECONCILIATION', 'SECURITY', 'CI', 'GO_NO_GO'])
    parser.add_argument('--status', required=True, choices=['PASS', 'FAIL', 'PENDING'])
    parser.add_argument('--started-at')
    parser.add_argument('--ended-at')
    parser.add_argument('--approved-by')
    parser.add_argument('--metrics-json', default='{}')
    args = parser.parse_args()

    settings = Settings()
    runtime = build_runtime_config()
    metrics = json.loads(args.metrics_json)
    db = Database(settings.database_url)
    db.open()
    try:
        repo = Repository(db)
        repo.record_go_no_go_evidence(
            evidence_type=args.type,
            status=args.status,
            config_hash=runtime.config_hash,
            trace_id=new_trace_id('gonogo'),
            metrics=metrics,
            started_at=args.started_at,
            ended_at=args.ended_at,
            approved_by=args.approved_by,
        )
    finally:
        db.close()
    print(json.dumps({'status': 'ok', 'evidence_type': args.type, 'config_hash': runtime.config_hash}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

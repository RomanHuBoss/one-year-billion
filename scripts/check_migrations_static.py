#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path


def main() -> int:
    sql = Path('migrations/0001_core_schema.sql').read_text(encoding='utf-8')
    failures: list[str] = []
    if sql.count('trade_id UUID PRIMARY KEY') != 1:
        failures.append('trades_journal_duplicate_primary_key')
    required = [
        'CREATE TRIGGER trg_validate_order_risk_decision',
        'active_position_protected CHECK',
        'one_pending_entry_per_symbol',
        'manual_reduce_only CHECK',
        'CREATE TABLE IF NOT EXISTS go_no_go_evidence',
        'go_no_go_pass_requires_approver CHECK',
    ]
    for token in required:
        if token not in sql:
            failures.append(f'missing:{token}')
    if failures:
        print('FAIL:', ';'.join(failures))
        return 2
    print('OK: migration static invariants present')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path


def main() -> int:
    sql = '\n'.join(path.read_text(encoding='utf-8') for path in sorted(Path('migrations').glob('*.sql')))
    failures: list[str] = []
    if sql.count('trade_id UUID PRIMARY KEY') != 1:
        failures.append('trades_journal_duplicate_primary_key')
    required = [
        'CREATE TRIGGER trg_validate_order_risk_decision',
        'active_position_protected CHECK',
        'one_pending_entry_per_symbol',
        'manual_reduce_only CHECK',
        'REJECTED_UNSAFE_ACTION',
        'CREATE TABLE IF NOT EXISTS go_no_go_evidence',
        'go_no_go_pass_requires_approver CHECK',
        'risk_approved_sizing_values_sane',
        'signals_product_scope_guard',
        'signals_trade_candidate_requires_lineage',
        'active_position_nonflat_qty',
        'manual_config_change_reduce_only',
        'order qty exceeds approved risk sizing',
        'risk_decision feature_hash mismatch',
        'AS severity',
        'AS allowed_actions',
        'AS updated_at',
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

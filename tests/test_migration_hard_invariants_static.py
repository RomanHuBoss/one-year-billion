from pathlib import Path


def _all_sql() -> str:
    return '\n'.join(path.read_text(encoding='utf-8') for path in sorted(Path('migrations').glob('*.sql')))


def test_db_hard_invariants_cover_risk_signal_order_lineage():
    sql = _all_sql()
    for token in [
        'risk_approved_sizing_values_sane',
        "(sizing_json->>'max_loss_if_stop')::numeric <= (sizing_json->>'risk_budget')::numeric",
        "(sizing_json->>'expected_net_edge_bps')::numeric > 0",
        'signals_product_scope_guard',
        'signals_trade_candidate_requires_lineage',
        'signal has no live order route',
        'risk_decision feature_hash mismatch',
        'order qty exceeds approved risk sizing',
        'order notional exceeds approved risk sizing',
        'min_qty > 0',
        'min_notional > 0',
        'max_leverage > 0',
    ]:
        assert token in sql


def test_db_hard_invariants_cover_active_and_manual_override():
    sql = _all_sql()
    for token in [
        'active_position_protected CHECK',
        'active_position_nonflat_qty',
        'manual_reduce_only CHECK',
        'manual_config_change_reduce_only',
        "action NOT IN ('PROPOSE_CONFIG','ACTIVATE_CONFIG')",
        "coalesce(lower(target->>'risk_change'), 'same') IN ('same','decrease','risk_decrease')",
        "coalesce(lower(target->>'risk_increase'), 'false') NOT IN ('true','1','yes','on')",
    ]:
        assert token in sql

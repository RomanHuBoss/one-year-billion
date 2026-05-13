from datetime import timedelta
from app.core.time import utc_now
from app.execution.idempotency import deterministic_order_link_id
from app.execution.order_router import OrderRouter
from app.schemas.domain import RiskDecision, Side, SignalCandidate, SizingResult


def approved_risk(signal):
    now = utc_now()
    return RiskDecision(risk_decision_id='r1', signal_id=signal.signal_id, approved=True, reasons=[], sizing=SizingResult(qty=0.001, notional=100, risk_budget=5, stop_distance_abs=1000, max_loss_if_stop=2, expected_net_edge_bps=10), limits_snapshot={}, account_snapshot={}, specs_version='x', feature_hash=signal.feature_hash, config_hash='cfg', trace_id=signal.trace_id, created_at=now, expires_at=now+timedelta(seconds=60))


def test_order_link_id_len():
    oid = deterministic_order_link_id('s'*64, 'r'*64, 'entry')
    assert len(oid) <= 36


def test_idempotency_returns_same_intent():
    signal = SignalCandidate(
        signal_id='s1', strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY,
        entry_price=100000, stop_price=99000, invalidator='x', expected_gross_edge_bps=30,
        required_data=['range_bounds'], regime_id='reg-1', feature_id='feat-1',
        trace_id='t1', strategy_version='1', feature_hash='fh', evidence={'range_quality': 'ok'},
    )
    risk = approved_risk(signal)
    router = OrderRouter()
    a = router.build_intent(signal, risk, 'key1')
    b = router.build_intent(signal, risk, 'key1')
    assert a.order_id == b.order_id
    assert a.client_order_id == b.client_order_id


def test_order_router_rejects_incomplete_signal_lineage_even_with_approved_risk():
    signal = SignalCandidate(
        signal_id='s-lineage', strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY,
        entry_price=100000, stop_price=99000, invalidator='range_break', expected_gross_edge_bps=30,
        trace_id='t-lineage', strategy_version='1', feature_hash='fh-lineage', evidence={'range_quality': 'ok'},
    )
    risk = approved_risk(signal)
    router = OrderRouter()
    import pytest
    with pytest.raises(ValueError, match='incomplete_signal_lineage'):
        router.build_intent(signal, risk, 'key-lineage')


def test_order_router_rejects_claimed_approved_risk_that_breaks_budget():
    signal = SignalCandidate(
        signal_id='s-budget', strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY,
        entry_price=100000, stop_price=99000, invalidator='range_break', expected_gross_edge_bps=30,
        required_data=['range_bounds'], regime_id='reg-budget', feature_id='feat-budget',
        trace_id='t-budget', strategy_version='1', feature_hash='fh-budget', evidence={'range_quality': 'ok'},
    )
    risk = approved_risk(signal)
    risk.sizing.max_loss_if_stop = risk.sizing.risk_budget + 0.01
    router = OrderRouter()
    import pytest
    with pytest.raises(ValueError, match='approved_sizing_breaks_risk_budget'):
        router.build_intent(signal, risk, 'key-budget')

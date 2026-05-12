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
    signal = SignalCandidate(signal_id='s1', strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY, entry_price=100000, stop_price=99000, invalidator='x', expected_gross_edge_bps=30, trace_id='t1', strategy_version='1', feature_hash='fh')
    risk = approved_risk(signal)
    router = OrderRouter()
    a = router.build_intent(signal, risk, 'key1')
    b = router.build_intent(signal, risk, 'key1')
    assert a.order_id == b.order_id
    assert a.client_order_id == b.client_order_id

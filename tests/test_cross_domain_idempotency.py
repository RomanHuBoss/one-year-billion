from datetime import timedelta
from app.core.time import utc_now
from app.execution.idempotency import InMemoryIdempotencyStore, namespaced_idempotency_key
from app.execution.order_router import OrderRouter
from app.schemas.domain import RiskDecision, Side, SignalCandidate, SizingResult


def _signal() -> SignalCandidate:
    return SignalCandidate(
        signal_id='s-cross', strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY,
        entry_price=100000, stop_price=99000, invalidator='range_break',
        expected_gross_edge_bps=30, trace_id='t-cross', strategy_version='1',
        feature_hash='fh-cross', evidence={'range_quality': 'ok'},
    )


def _risk(signal: SignalCandidate) -> RiskDecision:
    now = utc_now()
    return RiskDecision(
        risk_decision_id='r-cross', signal_id=signal.signal_id, approved=True, reasons=[],
        sizing=SizingResult(qty=0.001, notional=100, risk_budget=5, stop_distance_abs=1000, max_loss_if_stop=2, expected_net_edge_bps=10),
        limits_snapshot={}, account_snapshot={}, specs_version='runtime-v1',
        feature_hash=signal.feature_hash, config_hash='cfg', trace_id=signal.trace_id,
        created_at=now, expires_at=now + timedelta(seconds=60),
    )


def test_manual_and_order_idempotency_keys_are_isolated():
    store = InMemoryIdempotencyStore()
    store.put(namespaced_idempotency_key('manual', 'same-user-key'), {'status': 'ok'})
    signal = _signal()
    intent = OrderRouter(store).build_intent(signal, _risk(signal), 'same-user-key')
    assert intent.signal_id == signal.signal_id
    assert store.get(namespaced_idempotency_key('manual', 'same-user-key')) == {'status': 'ok'}

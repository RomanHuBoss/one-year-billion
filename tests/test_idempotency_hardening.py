from datetime import timedelta
import pytest
from app.core.time import utc_now
from app.execution.idempotency import InMemoryIdempotencyStore
from app.execution.order_router import OrderRouter
from app.schemas.domain import RiskDecision, Side, SignalCandidate, SizingResult


def make_signal(signal_id: str, symbol: str = 'BTCUSDT') -> SignalCandidate:
    return SignalCandidate(
        signal_id=signal_id,
        strategy='micro_grid',
        symbol=symbol,
        side=Side.BUY,
        entry_price=100000,
        stop_price=99000,
        invalidator='range_break',
        expected_gross_edge_bps=30,
        trace_id=f't-{signal_id}',
        strategy_version='1',
        feature_hash=f'fh-{signal_id}',
        evidence={'range_quality': 'ok'},
    )


def make_risk(signal: SignalCandidate) -> RiskDecision:
    now = utc_now()
    return RiskDecision(
        risk_decision_id=f'r-{signal.signal_id}',
        signal_id=signal.signal_id,
        approved=True,
        reasons=[],
        sizing=SizingResult(qty=0.001, notional=100, risk_budget=5, stop_distance_abs=1000, max_loss_if_stop=2, expected_net_edge_bps=10),
        limits_snapshot={},
        account_snapshot={},
        specs_version='runtime-v1',
        feature_hash=signal.feature_hash,
        config_hash='cfg',
        trace_id=signal.trace_id,
        created_at=now,
        expires_at=now + timedelta(seconds=60),
    )


def test_symbol_lock_is_shared_across_router_instances():
    store = InMemoryIdempotencyStore()
    first_router = OrderRouter(store)
    second_router = OrderRouter(store)
    first = make_signal('s1')
    first_router.build_intent(first, make_risk(first), 'key-1')
    second = make_signal('s2')
    with pytest.raises(ValueError, match='symbol_locked_pending_execution'):
        second_router.build_intent(second, make_risk(second), 'key-2')


def test_idempotency_key_cannot_be_reused_for_different_signal():
    router = OrderRouter()
    first = make_signal('s1')
    router.build_intent(first, make_risk(first), 'same-key')
    second = make_signal('s2')
    with pytest.raises(ValueError, match='idempotency_key_reused_with_different_request'):
        router.build_intent(second, make_risk(second), 'same-key')

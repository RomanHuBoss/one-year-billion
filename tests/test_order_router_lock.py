from datetime import timedelta
import pytest
from app.core.time import utc_now
from app.execution.order_router import OrderRouter
from app.schemas.domain import RiskDecision, Side, SignalCandidate, SizingResult


def make_signal(signal_id: str) -> SignalCandidate:
    return SignalCandidate(signal_id=signal_id, strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY, entry_price=100000, stop_price=99000, invalidator='range_break', expected_gross_edge_bps=30, trace_id='t', strategy_version='1', feature_hash='fh', evidence={'x': 1})


def make_risk(signal: SignalCandidate) -> RiskDecision:
    now = utc_now()
    return RiskDecision(risk_decision_id=f'r-{signal.signal_id}', signal_id=signal.signal_id, approved=True, reasons=[], sizing=SizingResult(qty=0.001, notional=100, risk_budget=5, stop_distance_abs=1000, max_loss_if_stop=2, expected_net_edge_bps=10), limits_snapshot={}, account_snapshot={}, specs_version='x', feature_hash=signal.feature_hash, config_hash='cfg', trace_id=signal.trace_id, created_at=now, expires_at=now+timedelta(seconds=60))


def test_symbol_lock_blocks_second_entry_path():
    router = OrderRouter()
    first = make_signal('s1')
    router.build_intent(first, make_risk(first), 'key-1')
    second = make_signal('s2')
    with pytest.raises(ValueError, match='symbol_locked_pending_execution'):
        router.build_intent(second, make_risk(second), 'key-2')


def test_symbol_lock_allows_after_release():
    router = OrderRouter()
    first = make_signal('s1')
    router.build_intent(first, make_risk(first), 'key-1')
    router.release_symbol('BTCUSDT', 'key-1')
    second = make_signal('s2')
    intent = router.build_intent(second, make_risk(second), 'key-2')
    assert intent.signal_id == 's2'

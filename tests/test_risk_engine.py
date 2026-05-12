from datetime import timedelta
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, MLVerdict, MLVerdictType, Side, SignalCandidate
from app.risk_engine.approval import approve_signal, RiskConfig


def base_objects():
    now = utc_now()
    account = AccountSnapshot(equity_usdt=500, available_balance_usdt=500, phase=0, fetched_at=now, expires_at=now+timedelta(minutes=5))
    specs = InstrumentSpec(symbol='BTCUSDT', tick_size=0.1, qty_step=0.001, min_qty=0.001, min_notional=5, max_leverage=100, specs_version='test', fetched_at=now, expires_at=now+timedelta(minutes=5))
    market = MarketSnapshot(symbol='BTCUSDT', bid1=100000, ask1=100001, spread_bps=0.1, depth_usdt=5_000_000, fetched_at=now, expires_at=now+timedelta(seconds=30))
    signal = SignalCandidate(signal_id='s1', strategy='micro_grid', symbol='BTCUSDT', side=Side.BUY, entry_price=100000, stop_price=99000, invalidator='range_break', expected_gross_edge_bps=30, trace_id='t1', strategy_version='1', feature_hash='fh')
    ml = MLVerdict(verdict=MLVerdictType.ALLOW, required=False, block=False)
    return signal, ml, account, market, specs


def test_missing_stop_rejected():
    signal, ml, account, market, specs = base_objects()
    signal.stop_price = None
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'missing_stop_or_invalidator' in rd.reasons


def test_no_net_edge_rejected():
    signal, ml, account, market, specs = base_objects()
    signal.expected_gross_edge_bps = 1
    rd = approve_signal(signal, ml, account, market, specs)
    assert not rd.approved
    assert 'no_net_edge_after_costs' in rd.reasons


def test_min_notional_does_not_force_oversize():
    signal, ml, account, market, specs = base_objects()
    specs.min_notional = 1_000_000
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'min_qty_or_notional' in rd.reasons


def test_symbol_runtime_mismatch_rejected():
    signal, ml, account, market, specs = base_objects()
    specs.symbol = 'ETHUSDT'
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'symbol_runtime_mismatch' in rd.reasons


def test_nonpositive_gross_edge_rejected_before_execution():
    signal, ml, account, market, specs = base_objects()
    signal.expected_gross_edge_bps = 0
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'missing_or_nonpositive_gross_edge' in rd.reasons

from datetime import timedelta
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, MLVerdict, MLVerdictType, Side, SignalCandidate
from app.risk_engine.approval import approve_signal, RiskConfig


def base_objects():
    now = utc_now()
    account = AccountSnapshot(equity_usdt=500, available_balance_usdt=500, phase=0, fetched_at=now, expires_at=now+timedelta(minutes=5))
    specs = InstrumentSpec(symbol='BTCUSDT', tick_size=0.1, qty_step=0.001, min_qty=0.001, min_notional=5, max_leverage=100, specs_version='test', fetched_at=now, expires_at=now+timedelta(minutes=5))
    market = MarketSnapshot(symbol='BTCUSDT', bid1=100000, ask1=100001, spread_bps=0.1, depth_usdt=5_000_000, funding_fresh=True, fetched_at=now, expires_at=now+timedelta(seconds=30))
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


def test_reserve_cash_uses_initial_margin_not_only_costs():
    signal, ml, account, market, specs = base_objects()
    # Очень широкий stop снижает qty, но цена делает notional близким к equity.
    # Старый расчет резерва вычитал только costs и пропускал такую заявку.
    signal.entry_price = 100000
    signal.stop_price = 99500
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0, reserve_cash_pct=0.80, max_effective_leverage=3.0))
    assert not rd.approved
    assert 'reserve_cash_violation' in rd.reasons


def test_daily_and_weekly_remaining_risk_are_hard_caps():
    signal, ml, account, market, specs = base_objects()
    account.realized_negative_today_usdt = account.equity_usdt * 0.03
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'daily_remaining_risk_exhausted' in rd.reasons


def test_portfolio_abs_exposure_cap_blocks_candidate():
    signal, ml, account, market, specs = base_objects()
    account.portfolio_abs_notional_usdt = 499
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0, max_portfolio_abs_notional_usdt=500))
    assert not rd.approved
    assert 'portfolio_abs_exposure_cap' in rd.reasons


def test_invalid_instrument_specs_fail_closed_without_exception():
    signal, ml, account, market, specs = base_objects()
    specs.qty_step = 0
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_instrument_specs' in rd.reasons
    assert any(reason.startswith('sizing_failed:') for reason in rd.reasons)


def test_stale_funding_rejected_fail_closed():
    signal, ml, account, market, specs = base_objects()
    market.funding_fresh = False
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'stale_funding' in rd.reasons


def test_carry_live_rejected_in_phase_0_even_if_not_marked_shadow():
    signal, ml, account, market, specs = base_objects()
    signal.strategy = 'carry_live'
    signal.shadow_only = False
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'strategy_shadow_only' in rd.reasons


def test_forbidden_product_strategy_rejected_by_risk_engine():
    signal, ml, account, market, specs = base_objects()
    signal.strategy = 'martingale'
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'strategy_forbidden_product_scope' in rd.reasons


def test_effective_leverage_uses_total_portfolio_exposure():
    signal, ml, account, market, specs = base_objects()
    account.portfolio_abs_notional_usdt = 1490
    # Candidate by itself is tiny, but total portfolio exposure exceeds 3x equity.
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0, max_effective_leverage=3.0))
    assert not rd.approved
    assert 'leverage_cap' in rd.reasons
    assert rd.sizing.effective_leverage > 3.0


def test_beta_adjusted_exposure_cap_defaults_to_effective_leverage_cap():
    signal, ml, account, market, specs = base_objects()
    account.beta_adjusted_exposure_usdt = 1490
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0, max_effective_leverage=3.0))
    assert not rd.approved
    assert 'beta_adjusted_exposure_cap' in rd.reasons


def test_zero_min_qty_and_min_notional_fail_closed():
    signal, ml, account, market, specs = base_objects()
    specs.min_qty = 0
    specs.min_notional = 0
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_instrument_specs' in rd.reasons


def test_invalid_market_snapshot_fail_closed_before_cost_model_can_help():
    signal, ml, account, market, specs = base_objects()
    market.ask1 = market.bid1 - 1
    market.spread_bps = -1
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_market_snapshot' in rd.reasons


def test_zero_account_equity_rejected_fail_closed():
    signal, ml, account, market, specs = base_objects()
    account.equity_usdt = 0
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_account_equity' in rd.reasons


def test_nan_signal_edge_rejected_fail_closed():
    signal, ml, account, market, specs = base_objects()
    signal.expected_gross_edge_bps = float('nan')
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_signal_numeric_value' in rd.reasons


def test_infinite_entry_price_rejected_fail_closed():
    signal, ml, account, market, specs = base_objects()
    signal.entry_price = float('inf')
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_signal_numeric_value' in rd.reasons


def test_negative_cost_model_rejected_fail_closed():
    from app.risk_engine.cost_model import CostModel
    signal, ml, account, market, specs = base_objects()
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(min_net_edge_bps=0), CostModel(maker_fee_bps=-1))
    assert not rd.approved
    assert 'invalid_cost_model' in rd.reasons


def test_nonfinite_risk_config_rejected_fail_closed():
    signal, ml, account, market, specs = base_objects()
    rd = approve_signal(signal, ml, account, market, specs, RiskConfig(risk_pct_default=float('nan'), min_net_edge_bps=0))
    assert not rd.approved
    assert 'invalid_risk_config' in rd.reasons

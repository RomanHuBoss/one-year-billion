from __future__ import annotations
from datetime import timedelta
import pytest
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision
from app.strategies.carry_shadow import CarryShadowScanner
from app.strategies.statarb_shadow import StatArbShadowScanner
from app.execution.order_router import OrderRouter
from app.risk_engine.approval import approve_signal
from app.ml.inference import MLGate
from app.schemas.domain import InstrumentSpec


def _account() -> AccountSnapshot:
    now = utc_now()
    return AccountSnapshot(equity_usdt=500, available_balance_usdt=500, phase=0, fetched_at=now, expires_at=now + timedelta(seconds=30))


def _market(**overrides) -> MarketSnapshot:
    now = utc_now()
    base = dict(
        symbol='BTCUSDT', bid1=100.0, ask1=100.1, spread_bps=1.0, depth_usdt=2_000_000,
        funding_bps=8.0, funding_fresh=True, funding_sanity=True, atr_pct=0.01,
        volume_z=1.0, range_width_bps=30.0, adx=12, fetched_at=now, expires_at=now + timedelta(seconds=30),
    )
    base.update(overrides)
    return MarketSnapshot(**base)


def _regime(regime: Regime = Regime.RANGE) -> RegimeDecision:
    return RegimeDecision(regime_id='reg-shadow', symbol='BTCUSDT', regime=regime, confidence=0.8, reasons=[], thresholds_snapshot={}, trace_id='trace-shadow')


def _spec() -> InstrumentSpec:
    now = utc_now()
    return InstrumentSpec(symbol='BTCUSDT', category='linear', status='Trading', tick_size=0.1, qty_step=0.001, min_qty=0.001, min_notional=5, max_leverage=5, specs_version='v-test', fetched_at=now, expires_at=now + timedelta(seconds=30))


@pytest.mark.parametrize('scanner', [CarryShadowScanner(), StatArbShadowScanner()])
def test_shadow_scanners_emit_shadow_only_candidates(scanner):
    candidates = scanner.propose(_market(), _account(), _regime())
    assert candidates
    assert all(candidate.shadow_only for candidate in candidates)
    assert all(candidate.stop_price is not None and candidate.invalidator for candidate in candidates)
    assert all(candidate.evidence for candidate in candidates)


def test_shadow_candidate_cannot_reach_risk_or_order_route():
    candidate = CarryShadowScanner().propose(_market(), _account(), _regime())[0]
    ml = MLGate().evaluate(candidate)
    risk = approve_signal(candidate, ml, _account(), _market(), _spec())
    assert not risk.approved
    assert 'strategy_shadow_only' in risk.reasons
    with pytest.raises(ValueError, match='shadow_signal_has_no_live_route'):
        OrderRouter().build_intent(candidate, risk, 'shadow-route')

from datetime import timedelta
from app.core.time import utc_now
from app.regime.classifier import RegimeClassifier
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision
from app.strategies.breakout import LimitedBreakoutStrategy
from app.strategies.micro_grid import MicroGridStrategy


def _account():
    now = utc_now()
    return AccountSnapshot(equity_usdt=500, available_balance_usdt=500, fetched_at=now, expires_at=now+timedelta(minutes=5))


def _regime(regime):
    return RegimeDecision(regime_id='reg-1', symbol='BTCUSDT', regime=regime, confidence=0.8, reasons=[], thresholds_snapshot={}, trace_id='tr')


def _market(**kwargs):
    now = utc_now()
    data = dict(symbol='BTCUSDT', bid1=100000, ask1=100001, spread_bps=0.1, depth_usdt=5_000_000, atr_pct=0.015, volume_z=2.2, btc_aligned=True, fetched_at=now, expires_at=now+timedelta(seconds=30))
    data.update(kwargs)
    return MarketSnapshot(**data)


def test_breakout_requires_structure_or_donchian_confirmation():
    strat = LimitedBreakoutStrategy()
    assert strat.propose(_market(structure_break=False, donchian_break=False), _account(), _regime(Regime.TREND_UP)) == []
    result = strat.propose(_market(structure_break=True, atr_expansion=True, oi_sanity=True, funding_sanity=True), _account(), _regime(Regime.TREND_UP))
    assert len(result) == 1
    cand = result[0]
    assert cand.requires_ml is True
    assert 'donchian_or_structure_break' in cand.required_data
    assert cand.evidence['structure_or_donchian_break'] is True


def test_micro_grid_evidence_prevents_martingale_shape():
    strat = MicroGridStrategy()
    result = strat.propose(_market(range_width_bps=40, adx=12), _account(), _regime(Regime.RANGE))
    assert len(result) == 1
    cand = result[0]
    assert cand.stop_price is not None
    assert cand.evidence['max_inventory'] == 1
    assert cand.evidence['no_add_after_invalidation'] is True
    assert cand.invalidator == 'range_break_or_btc_impulse'


def test_micro_grid_rejects_trending_adx():
    strat = MicroGridStrategy()
    assert strat.propose(_market(range_width_bps=40, adx=30), _account(), _regime(Regime.RANGE)) == []

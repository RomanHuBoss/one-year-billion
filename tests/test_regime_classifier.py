from datetime import timedelta
from app.core.time import utc_now
from app.regime.classifier import RegimeClassifier, safer_regime, strategy_allowed
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime


def _account(**kwargs):
    now = utc_now()
    data = dict(equity_usdt=500, available_balance_usdt=500, fetched_at=now, expires_at=now+timedelta(minutes=5))
    data.update(kwargs)
    return AccountSnapshot(**data)


def _market(**kwargs):
    now = utc_now()
    data = dict(symbol='BTCUSDT', bid1=100000, ask1=100001, spread_bps=0.1, depth_usdt=5_000_000, atr_pct=0.015, volume_z=2.2, btc_aligned=True, fetched_at=now, expires_at=now+timedelta(seconds=30))
    data.update(kwargs)
    return MarketSnapshot(**data)


def test_priority_chooses_safer_mixed_regime():
    assert safer_regime(Regime.RANGE, Regime.NO_TRADE, Regime.HIGH_VOL) == Regime.NO_TRADE
    clf = RegimeClassifier()
    decision = clf.classify(_market(oi_delta_pct=-15, volatility_bps=300), _account())
    assert decision.regime == Regime.LIQUIDATION
    assert any('mixed_regime_choose_safer' in r for r in decision.reasons)


def test_hysteresis_blocks_first_normal_flip_to_less_safe_state():
    clf = RegimeClassifier(hysteresis_bars=2)
    first = clf.classify(_market(atr_pct=0.015, volume_z=0.2), _account())
    assert first.regime == Regime.RANGE
    second = clf.classify(_market(atr_pct=0.02, volume_z=2.3, btc_aligned=True), _account())
    assert second.regime == Regime.TREND_UP
    third = clf.classify(_market(atr_pct=0.015, volume_z=0.2), _account())
    assert third.regime == Regime.TREND_UP
    assert any('hysteresis_pending' in r for r in third.reasons)
    fourth = clf.classify(_market(atr_pct=0.015, volume_z=0.2), _account())
    assert fourth.regime == Regime.RANGE


def test_immediate_kill_switch_and_permissions():
    clf = RegimeClassifier(hysteresis_bars=5)
    decision = clf.classify(_market(), _account(), kill_switch=True)
    assert decision.regime == Regime.DE_RISK
    allowed, reason = strategy_allowed('micro_grid', Regime.DE_RISK, 0)
    assert not allowed
    assert reason == 'grid_forbidden_outside_range'

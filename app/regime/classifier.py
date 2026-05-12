from __future__ import annotations
from uuid import uuid4
from app.core.hashes import new_trace_id
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision

PRIORITY = [Regime.DE_RISK, Regime.NO_TRADE, Regime.NEWS_RISK, Regime.LIQUIDATION, Regime.HIGH_VOL, Regime.TREND_UP, Regime.TREND_DOWN, Regime.RANGE, Regime.LOW_VOL]


class RegimeClassifier:
    def classify(self, market: MarketSnapshot, account: AccountSnapshot, kill_switch: bool = False, news_risk: bool = False) -> RegimeDecision:
        reasons: list[str] = []
        regime = Regime.NO_TRADE
        confidence = 0.5
        if kill_switch or account.daily_loss_hit or account.weekly_loss_hit:
            regime = Regime.DE_RISK
            reasons.append('kill_switch_or_loss_limit')
            confidence = 1.0
        elif news_risk:
            regime = Regime.NEWS_RISK
            reasons.append('llm_or_operator_news_risk')
            confidence = 0.8
        elif not market.fresh or not account.fresh:
            regime = Regime.NO_TRADE
            reasons.append('stale_market_or_account')
            confidence = 1.0
        elif market.volatility_bps > 250 or market.atr_pct > 0.04:
            regime = Regime.HIGH_VOL
            reasons.append('high_volatility')
            confidence = 0.7
        elif market.volume_z >= 2 and market.atr_pct >= 0.012 and market.btc_aligned:
            regime = Regime.TREND_UP
            reasons.append('volume_expansion_btc_aligned')
            confidence = 0.65
        elif market.atr_pct <= 0.018 and market.spread_bps <= 3.0:
            regime = Regime.RANGE
            reasons.append('low_atr_tight_spread')
            confidence = 0.6
        else:
            regime = Regime.NO_TRADE
            reasons.append('no_safe_permission')
        return RegimeDecision(
            regime_id=str(uuid4()), symbol=market.symbol, regime=regime, confidence=confidence,
            reasons=reasons, thresholds_snapshot={'atr_range_max': 0.018, 'volume_z_breakout': 2.0}, trace_id=new_trace_id('reg')
        )


def strategy_allowed(strategy: str, regime: Regime, phase: int) -> tuple[bool, str]:
    if strategy in {'carry_live', 'statarb_live'} and phase <= 1:
        return False, 'strategy_shadow_only_phase_0_1'
    if strategy == 'micro_grid' and regime != Regime.RANGE:
        return False, 'grid_forbidden_outside_range'
    if strategy == 'breakout' and regime not in {Regime.TREND_UP, Regime.TREND_DOWN, Regime.HIGH_VOL}:
        return False, 'breakout_requires_confirmed_shift'
    if regime in {Regime.DE_RISK, Regime.NO_TRADE, Regime.NEWS_RISK, Regime.LIQUIDATION} and strategy not in {'no_trade','de_risk'}:
        return False, 'regime_blocks_new_entries'
    return True, 'allowed'

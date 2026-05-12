from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import uuid4
from app.core.hashes import new_trace_id
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision

# Чем левее regime, тем безопаснее/приоритетнее он при смешанных сигналах.
PRIORITY = [Regime.DE_RISK, Regime.NO_TRADE, Regime.NEWS_RISK, Regime.LIQUIDATION, Regime.HIGH_VOL, Regime.TREND_UP, Regime.TREND_DOWN, Regime.RANGE, Regime.LOW_VOL]
_PRIORITY_INDEX = {regime: idx for idx, regime in enumerate(PRIORITY)}
_IMMEDIATE = {Regime.DE_RISK, Regime.NO_TRADE, Regime.NEWS_RISK, Regime.LIQUIDATION}
_NORMAL = {Regime.HIGH_VOL, Regime.TREND_UP, Regime.TREND_DOWN, Regime.RANGE, Regime.LOW_VOL}


def safer_regime(*regimes: Regime) -> Regime:
    """Возвращает более безопасный regime по нормативному priority order."""

    return min(regimes, key=lambda item: _PRIORITY_INDEX[item])


@dataclass
class _Memory:
    last_regime: dict[str, Regime] = field(default_factory=dict)
    pending_regime: dict[str, Regime] = field(default_factory=dict)
    pending_count: dict[str, int] = field(default_factory=dict)
    cooldown_until: dict[str, datetime] = field(default_factory=dict)


class RegimeClassifier:
    def __init__(self, hysteresis_bars: int = 2, cooldown_seconds: int = 300):
        self.hysteresis_bars = max(int(hysteresis_bars), 1)
        self.cooldown_seconds = max(int(cooldown_seconds), 0)
        self._memory = _Memory()

    def _raw_candidates(self, market: MarketSnapshot, account: AccountSnapshot, kill_switch: bool, news_risk: bool) -> tuple[list[Regime], list[str], float]:
        candidates: list[Regime] = []
        reasons: list[str] = []
        confidence = 0.5

        if kill_switch or account.daily_loss_hit or account.weekly_loss_hit:
            candidates.append(Regime.DE_RISK)
            reasons.append('kill_switch_or_loss_limit')
            confidence = 1.0
        if news_risk:
            candidates.append(Regime.NEWS_RISK)
            reasons.append('llm_or_operator_news_risk')
            confidence = max(confidence, 0.8)
        if not market.fresh or not account.fresh:
            candidates.append(Regime.NO_TRADE)
            reasons.append('stale_market_or_account')
            confidence = 1.0
        if market.oi_delta_pct <= -12.0 and market.volatility_bps > 120:
            candidates.append(Regime.LIQUIDATION)
            reasons.append('liquidation_or_oi_flush_risk')
            confidence = max(confidence, 0.85)
        if market.volatility_bps > 250 or market.atr_pct > 0.04:
            candidates.append(Regime.HIGH_VOL)
            reasons.append('high_volatility')
            confidence = max(confidence, 0.7)
        if market.volume_z >= 2 and market.atr_pct >= 0.012 and market.btc_aligned:
            candidates.append(Regime.TREND_UP)
            reasons.append('volume_expansion_btc_aligned')
            confidence = max(confidence, 0.65)
        if market.atr_pct <= 0.018 and market.spread_bps <= 3.0:
            candidates.append(Regime.RANGE)
            reasons.append('low_atr_tight_spread')
            confidence = max(confidence, 0.6)
        if market.atr_pct <= 0.006 and market.volume_z < 0.5:
            candidates.append(Regime.LOW_VOL)
            reasons.append('low_volatility_low_participation')
            confidence = max(confidence, 0.55)
        if not candidates:
            candidates.append(Regime.NO_TRADE)
            reasons.append('no_safe_permission')
        return candidates, reasons, confidence

    def _apply_cooldown_and_hysteresis(self, symbol: str, candidate: Regime, reasons: list[str], now: datetime) -> Regime:
        if candidate == Regime.DE_RISK and self.cooldown_seconds:
            self._memory.cooldown_until[symbol] = now + timedelta(seconds=self.cooldown_seconds)

        cooldown_until = self._memory.cooldown_until.get(symbol)
        if cooldown_until and now < cooldown_until and candidate in _NORMAL:
            reasons.append('regime_cooldown_no_new_entries')
            self._memory.last_regime[symbol] = Regime.NO_TRADE
            return Regime.NO_TRADE

        previous = self._memory.last_regime.get(symbol)
        if previous is None or candidate in _IMMEDIATE or previous in _IMMEDIATE or candidate == previous:
            self._memory.last_regime[symbol] = candidate
            self._memory.pending_regime.pop(symbol, None)
            self._memory.pending_count.pop(symbol, None)
            return candidate

        # Переход в более безопасный режим не ждем: это risk-reducing action.
        if _PRIORITY_INDEX[candidate] < _PRIORITY_INDEX[previous]:
            self._memory.last_regime[symbol] = candidate
            self._memory.pending_regime.pop(symbol, None)
            self._memory.pending_count.pop(symbol, None)
            return candidate

        if self.hysteresis_bars <= 1:
            self._memory.last_regime[symbol] = candidate
            return candidate

        if self._memory.pending_regime.get(symbol) != candidate:
            self._memory.pending_regime[symbol] = candidate
            self._memory.pending_count[symbol] = 1
            reasons.append(f'hysteresis_pending:{candidate.value}')
            return safer_regime(previous, candidate)

        self._memory.pending_count[symbol] = self._memory.pending_count.get(symbol, 0) + 1
        if self._memory.pending_count[symbol] >= self.hysteresis_bars:
            self._memory.last_regime[symbol] = candidate
            self._memory.pending_regime.pop(symbol, None)
            self._memory.pending_count.pop(symbol, None)
            return candidate

        reasons.append(f'hysteresis_wait:{candidate.value}:{self._memory.pending_count[symbol]}/{self.hysteresis_bars}')
        return safer_regime(previous, candidate)

    def classify(self, market: MarketSnapshot, account: AccountSnapshot, kill_switch: bool = False, news_risk: bool = False) -> RegimeDecision:
        now = utc_now()
        candidates, reasons, confidence = self._raw_candidates(market, account, kill_switch, news_risk)
        raw_regime = safer_regime(*candidates)
        if len(set(candidates)) > 1:
            reasons.append('mixed_regime_choose_safer:' + ','.join(r.value for r in candidates))
        regime = self._apply_cooldown_and_hysteresis(market.symbol, raw_regime, reasons, now)
        return RegimeDecision(
            regime_id=str(uuid4()), symbol=market.symbol, regime=regime, confidence=confidence,
            reasons=reasons,
            thresholds_snapshot={
                'priority': [r.value for r in PRIORITY],
                'atr_range_max': 0.018,
                'volume_z_breakout': 2.0,
                'hysteresis_bars': self.hysteresis_bars,
                'cooldown_seconds': self.cooldown_seconds,
            },
            trace_id=new_trace_id('reg')
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

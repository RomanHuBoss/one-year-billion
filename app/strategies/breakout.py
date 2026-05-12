from __future__ import annotations
from uuid import uuid4
from app.core.hashes import hash_payload, new_trace_id
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision, Side, SignalCandidate
from app.strategies.base import Strategy


class LimitedBreakoutStrategy(Strategy):
    name = 'breakout'
    version = '1.0.0'

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        if regime.regime not in {Regime.TREND_UP, Regime.TREND_DOWN, Regime.HIGH_VOL}:
            return []
        if market.volume_z < 2.0 or market.atr_pct < 0.012 or not market.btc_aligned:
            return []
        side = Side.BUY if regime.regime != Regime.TREND_DOWN else Side.SELL
        entry = market.ask1 if side == Side.BUY else market.bid1
        stop = entry * (0.985 if side == Side.BUY else 1.015)
        evidence = {'volume_z': market.volume_z, 'atr_pct': market.atr_pct, 'btc_aligned': market.btc_aligned}
        feature_hash = hash_payload({'symbol': market.symbol, 'strategy': self.name, 'evidence': evidence})
        return [SignalCandidate(
            signal_id=str(uuid4()), strategy=self.name, symbol=market.symbol, side=side,
            entry_price=entry, stop_price=stop, invalidator='failed_breakout_or_btc_alignment_lost',
            expected_gross_edge_bps=35.0, expected_holding_time_sec=3600,
            required_data=['closed_candles','orderbook','open_interest','funding'], regime_id=regime.regime_id,
            trace_id=new_trace_id('sig'), strategy_version=self.version, feature_hash=feature_hash,
            evidence=evidence, requires_ml=True, shadow_only=False,
        )]

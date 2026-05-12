from __future__ import annotations
from uuid import uuid4
from app.core.hashes import hash_payload, new_trace_id
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision, Side, SignalCandidate
from app.strategies.base import Strategy


class MicroGridStrategy(Strategy):
    name = 'micro_grid'
    version = '1.1.0-total-check'

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        if regime.regime != Regime.RANGE:
            return []
        range_width_bps = float(market.range_width_bps) if market.range_width_bps is not None else max(market.atr_pct * 10000, 1.0)
        # Grid допустим только как bounded mean-reversion: hard stop, max inventory=1,
        # запрет добавления после invalidation и ширина диапазона больше costs+buffer.
        if range_width_bps <= (market.spread_bps + 8.0):
            return []
        if market.adx is not None and market.adx > 22:
            return []
        if not market.funding_sanity:
            return []
        entry = market.bid1
        stop = entry * 0.985
        evidence = {
            'range_width_bps': range_width_bps,
            'spread_bps': market.spread_bps,
            'max_inventory': 1,
            'hard_stop': stop,
            'no_add_after_invalidation': True,
            'invalidation': 'range_break_or_btc_impulse',
            'funding_sanity_ok': market.funding_sanity,
            'adx': market.adx,
        }
        feature_hash = hash_payload({'symbol': market.symbol, 'strategy': self.name, 'evidence': evidence})
        return [SignalCandidate(
            signal_id=str(uuid4()), strategy=self.name, symbol=market.symbol, side=Side.BUY,
            entry_price=entry, stop_price=stop, invalidator='range_break_or_btc_impulse',
            expected_gross_edge_bps=18.0, expected_holding_time_sec=1800,
            required_data=['range_bounds','closed_candles','adx','orderbook','funding'], regime_id=regime.regime_id, feature_id=str(uuid4()),
            trace_id=new_trace_id('sig'), strategy_version=self.version, feature_hash=feature_hash,
            evidence=evidence, requires_ml=False, shadow_only=False,
        )]

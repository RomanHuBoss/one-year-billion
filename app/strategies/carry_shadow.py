from __future__ import annotations
from uuid import uuid4
from app.core.hashes import hash_payload, new_trace_id
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision, Side, SignalCandidate
from app.strategies.base import Strategy


class CarryShadowScanner(Strategy):
    name = 'carry_shadow'
    version = '1.1.0-total-check'

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        """Генерирует только SHADOW_SIGNAL для оценки funding/carry edge.

        Scanner нужен для накопления paper/shadow evidence, но не имеет live-route:
        candidate помечен shadow_only=True, а risk engine/order router дополнительно
        fail-closed отклоняют любой такой signal при попытке исполнения.
        """

        if regime.regime in {Regime.DE_RISK, Regime.NO_TRADE, Regime.NEWS_RISK, Regime.LIQUIDATION}:
            return []
        if not market.funding_fresh or not market.funding_sanity:
            return []
        # Funding edge должен быть измеримым после rough costs buffer. Это не
        # разрешение торговать: без hedge-quality/two-leg assembly Phase 0/1
        # остается только shadow-наблюдение.
        edge_after_spread = abs(float(market.funding_bps)) - float(market.spread_bps)
        if edge_after_spread <= 2.0:
            return []
        side = Side.SELL if market.funding_bps > 0 else Side.BUY
        entry = market.bid1 if side == Side.SELL else market.ask1
        stop = entry * (1.02 if side == Side.SELL else 0.98)
        evidence = {
            'shadow_reason': 'funding_carry_measurement_only',
            'funding_bps': market.funding_bps,
            'spread_bps': market.spread_bps,
            'rough_edge_after_spread_bps': edge_after_spread,
            'requires_phase_2_plus_for_live': True,
            'requires_two_leg_hedge_quality_proof': True,
            'no_live_route_phase_0_1': account.phase <= 1,
        }
        feature_hash = hash_payload({'symbol': market.symbol, 'strategy': self.name, 'evidence': evidence})
        return [SignalCandidate(
            signal_id=str(uuid4()), strategy=self.name, symbol=market.symbol, side=side,
            entry_price=entry, stop_price=stop, invalidator='funding_sign_flip_or_hedge_quality_fail',
            expected_gross_edge_bps=edge_after_spread, expected_holding_time_sec=8 * 3600,
            required_data=['funding', 'orderbook', 'fees', 'hedge_quality_shadow'],
            regime_id=regime.regime_id, feature_id=str(uuid4()), trace_id=new_trace_id('shadow'),
            strategy_version=self.version, feature_hash=feature_hash, evidence=evidence,
            requires_ml=False, shadow_only=True,
        )]

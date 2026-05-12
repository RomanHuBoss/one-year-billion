from __future__ import annotations
from uuid import uuid4
from app.core.hashes import hash_payload, new_trace_id
from app.schemas.domain import AccountSnapshot, MarketSnapshot, Regime, RegimeDecision, Side, SignalCandidate
from app.strategies.base import Strategy


class StatArbShadowScanner(Strategy):
    name = 'statarb_shadow'
    version = '1.1.0-total-check'

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        """Создает только shadow-кандидат для будущей pair stat-arb валидации.

        У MVP нет двухногого исполнения, поэтому scanner сохраняет измеримую
        аномалию как SHADOW_SIGNAL. Live route технически отсутствует.
        """

        if account.phase <= 1 and regime.regime not in {Regime.RANGE, Regime.LOW_VOL}:
            return []
        if not market.fresh or not market.funding_fresh:
            return []
        # Без отдельного pair context scanner не придумывает z-score. Он пишет
        # shadow-сигнал только при явной mean-reversion среде, где будущий pair
        # module сможет накапливать доказательства, не торгуя.
        if market.range_width_bps is None or market.adx is None or market.adx > 18:
            return []
        if float(market.range_width_bps) <= max(12.0, market.spread_bps + 8.0):
            return []
        entry = market.mid
        stop = entry * 0.985
        evidence = {
            'shadow_reason': 'pair_statarb_context_collection_only',
            'range_width_bps': market.range_width_bps,
            'adx': market.adx,
            'spread_bps': market.spread_bps,
            'requires_pair_beta_corr_zscore_inputs': True,
            'requires_two_leg_assembly_before_live': True,
            'no_live_route_phase_0_1': account.phase <= 1,
        }
        feature_hash = hash_payload({'symbol': market.symbol, 'strategy': self.name, 'evidence': evidence})
        return [SignalCandidate(
            signal_id=str(uuid4()), strategy=self.name, symbol=market.symbol, side=Side.BUY,
            entry_price=entry, stop_price=stop, invalidator='corr_beta_break_or_zscore_stop',
            expected_gross_edge_bps=max(float(market.range_width_bps) / 4.0, 1.0), expected_holding_time_sec=2 * 3600,
            required_data=['pair_beta', 'correlation', 'zscore', 'orderbook', 'funding'],
            regime_id=regime.regime_id, feature_id=str(uuid4()), trace_id=new_trace_id('shadow'),
            strategy_version=self.version, feature_hash=feature_hash, evidence=evidence,
            requires_ml=False, shadow_only=True,
        )]

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    maker_fee_bps: float = 2.0
    taker_fee_bps: float = 5.5
    slippage_buffer_bps: float = 2.0
    funding_buffer_bps: float = 1.0
    safety_buffer_bps: float = 2.0

    def round_trip_cost_bps(self, spread_bps: float, taker: bool = False, funding_bps: float = 0.0, hedge_cost_bps: float = 0.0) -> float:
        fee = self.taker_fee_bps if taker else self.maker_fee_bps
        # funding_buffer_bps учитывается всегда: фактический funding может измениться до выхода.
        return 2 * fee + spread_bps + self.slippage_buffer_bps + abs(funding_bps) + self.funding_buffer_bps + hedge_cost_bps + self.safety_buffer_bps

    def expected_net_edge_bps(self, gross_edge_bps: float, spread_bps: float, taker: bool = False, funding_bps: float = 0.0, hedge_cost_bps: float = 0.0) -> float:
        return gross_edge_bps - self.round_trip_cost_bps(spread_bps, taker, funding_bps, hedge_cost_bps)

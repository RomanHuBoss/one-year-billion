from __future__ import annotations
from app.schemas.domain import AccountSnapshot, MarketSnapshot, RegimeDecision, SignalCandidate
from app.strategies.base import Strategy


class CarryShadowScanner(Strategy):
    name = 'carry_shadow'
    version = '1.0.0'

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        # Phase 0/1 scanner only. It deliberately returns no live executable candidate.
        return []

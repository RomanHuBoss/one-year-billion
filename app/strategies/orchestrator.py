from __future__ import annotations
from app.regime.classifier import strategy_allowed
from app.schemas.domain import AccountSnapshot, MarketSnapshot, RegimeDecision, SignalCandidate
from app.strategies.breakout import LimitedBreakoutStrategy
from app.strategies.micro_grid import MicroGridStrategy


class StrategyOrchestrator:
    def __init__(self):
        self.strategies = [LimitedBreakoutStrategy(), MicroGridStrategy()]

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        candidates: list[SignalCandidate] = []
        for strategy in self.strategies:
            allowed, reason = strategy_allowed(strategy.name, regime.regime, account.phase)
            if not allowed:
                continue
            candidates.extend(strategy.propose(market, account, regime))
        return candidates

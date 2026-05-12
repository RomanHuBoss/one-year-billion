from __future__ import annotations
from app.regime.classifier import strategy_allowed
from app.schemas.domain import AccountSnapshot, MarketSnapshot, RegimeDecision, SignalCandidate
from app.strategies.breakout import LimitedBreakoutStrategy
from app.strategies.micro_grid import MicroGridStrategy
from app.strategies.carry_shadow import CarryShadowScanner
from app.strategies.statarb_shadow import StatArbShadowScanner


class StrategyOrchestrator:
    def __init__(self, include_shadow: bool = False):
        self.strategies = [LimitedBreakoutStrategy(), MicroGridStrategy()]
        self.shadow_strategies = [CarryShadowScanner(), StatArbShadowScanner()] if include_shadow else []

    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        candidates: list[SignalCandidate] = []
        for strategy in self.strategies:
            allowed, reason = strategy_allowed(strategy.name, regime.regime, account.phase)
            if not allowed:
                continue
            candidates.extend(strategy.propose(market, account, regime))
        for strategy in self.shadow_strategies:
            # Shadow scanners не проходят live permission matrix: они не должны
            # попадать в risk/execution. Здесь они нужны только для paper/shadow
            # evidence и всегда возвращают shadow_only=True.
            candidates.extend(c for c in strategy.propose(market, account, regime) if c.shadow_only)
        return candidates

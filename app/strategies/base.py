from __future__ import annotations
from abc import ABC, abstractmethod
from app.schemas.domain import AccountSnapshot, MarketSnapshot, RegimeDecision, SignalCandidate


class Strategy(ABC):
    name: str
    version: str = '1.0.0'

    @abstractmethod
    def propose(self, market: MarketSnapshot, account: AccountSnapshot, regime: RegimeDecision) -> list[SignalCandidate]:
        raise NotImplementedError

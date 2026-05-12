from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class Side(str, Enum):
    BUY = 'BUY'
    SELL = 'SELL'


class Regime(str, Enum):
    DE_RISK = 'DE_RISK'
    NO_TRADE = 'NO_TRADE'
    NEWS_RISK = 'NEWS_RISK'
    LIQUIDATION = 'LIQUIDATION'
    HIGH_VOL = 'HIGH_VOL'
    TREND_UP = 'TREND_UP'
    TREND_DOWN = 'TREND_DOWN'
    RANGE = 'RANGE'
    LOW_VOL = 'LOW_VOL'


class MLVerdictType(str, Enum):
    ALLOW = 'ALLOW'
    BLOCK = 'BLOCK'
    UNAVAILABLE = 'UNAVAILABLE'


class EffectiveStatus(str, Enum):
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    BLOCKED = 'BLOCKED'
    NO_TRADE = 'NO_TRADE'
    DE_RISK = 'DE_RISK'
    ERROR_RECONCILIATION_REQUIRED = 'ERROR_RECONCILIATION_REQUIRED'
    CLOSED = 'CLOSED'
    REJECTED = 'REJECTED'


class OrderState(str, Enum):
    PENDING_SIGNAL = 'PENDING_SIGNAL'
    RISK_REJECTED = 'RISK_REJECTED'
    APPROVED = 'APPROVED'
    ORDER_SUBMITTED = 'ORDER_SUBMITTED'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'
    PROTECTED_WITH_SLTP = 'PROTECTED_WITH_SLTP'
    REDUCE_ONLY_EXITING = 'REDUCE_ONLY_EXITING'
    CLOSED = 'CLOSED'
    ERROR_RECONCILIATION_REQUIRED = 'ERROR_RECONCILIATION_REQUIRED'
    BLOCKED = 'BLOCKED'
    DE_RISK = 'DE_RISK'


class InstrumentSpec(BaseModel):
    symbol: str
    category: str = 'linear'
    status: str = 'Trading'
    tick_size: float
    qty_step: float
    min_qty: float
    min_notional: float
    max_leverage: float
    specs_version: str
    fetched_at: datetime
    expires_at: datetime

    @property
    def fresh(self) -> bool:
        from app.core.time import utc_now
        return self.expires_at > utc_now()


class MarketSnapshot(BaseModel):
    symbol: str
    bid1: float
    ask1: float
    spread_bps: float
    depth_usdt: float
    funding_bps: float = 0.0
    volatility_bps: float = 0.0
    atr_pct: float = 0.0
    volume_z: float = 0.0
    oi_delta_pct: float = 0.0
    btc_aligned: bool = True
    fetched_at: datetime
    expires_at: datetime

    @property
    def mid(self) -> float:
        return (self.bid1 + self.ask1) / 2

    @property
    def fresh(self) -> bool:
        from app.core.time import utc_now
        return self.expires_at > utc_now()


class AccountSnapshot(BaseModel):
    equity_usdt: float
    available_balance_usdt: float
    phase: int = 0
    account_mode: str = 'runtime_checked'
    position_mismatch: bool = False
    daily_loss_hit: bool = False
    weekly_loss_hit: bool = False
    fetched_at: datetime
    expires_at: datetime

    @property
    def fresh(self) -> bool:
        from app.core.time import utc_now
        return self.expires_at > utc_now()


class RegimeDecision(BaseModel):
    regime_id: str
    symbol: str
    regime: Regime
    confidence: float
    reasons: list[str]
    thresholds_snapshot: dict[str, Any]
    trace_id: str


class SignalCandidate(BaseModel):
    signal_id: str
    strategy: str
    symbol: str
    side: Side
    entry_price: float
    stop_price: float | None = None
    invalidator: str | None = None
    expected_gross_edge_bps: float
    expected_holding_time_sec: int = 0
    required_data: list[str] = Field(default_factory=list)
    regime_id: str | None = None
    feature_id: str | None = None
    trace_id: str
    strategy_version: str
    feature_hash: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    requires_ml: bool = False
    shadow_only: bool = False

    @field_validator('symbol')
    @classmethod
    def symbol_upper(cls, value: str) -> str:
        return value.upper()


class MLVerdict(BaseModel):
    verdict: MLVerdictType
    required: bool = False
    block: bool = False
    reason: str = ''
    p_hit_2r: float | None = None
    uncertainty: float | None = None
    model_id: str | None = None
    feature_schema_hash: str | None = None


class SizingResult(BaseModel):
    qty: float = 0.0
    notional: float = 0.0
    risk_budget: float = 0.0
    stop_distance_abs: float = 0.0
    stop_distance_pct: float = 0.0
    max_loss_if_stop: float = 0.0
    effective_leverage: float = 0.0
    reserve_cash_after_pct: float = 1.0
    liquidation_distance_pct: float = 1.0
    expected_net_edge_bps: float = 0.0


class RiskDecision(BaseModel):
    risk_decision_id: str
    signal_id: str
    approved: bool
    reasons: list[str]
    sizing: SizingResult
    limits_snapshot: dict[str, Any]
    account_snapshot: dict[str, Any]
    specs_version: str
    feature_hash: str
    config_hash: str
    trace_id: str
    created_at: datetime
    expires_at: datetime

    @property
    def expired(self) -> bool:
        from app.core.time import utc_now
        return self.expires_at <= utc_now()


class OrderIntent(BaseModel):
    order_id: str
    signal_id: str
    risk_decision_id: str
    client_order_id: str
    symbol: str
    side: Side
    order_type: Literal['Limit','Market','PostOnly'] = 'Limit'
    qty: float
    price: float | None = None
    reduce_only: bool = False
    state: OrderState = OrderState.APPROVED
    idempotency_key: str
    trace_id: str


class PositionState(BaseModel):
    symbol: str
    side: Literal['LONG','SHORT','FLAT']
    qty: float
    avg_price: float | None = None
    liq_price: float | None = None
    sl_price: float | None = None
    tp_price: float | None = None
    state: str = 'FLAT'
    protection_state: str = 'NONE'
    reconciliation_status: str = 'UNKNOWN'
    trace_id: str

from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, MLVerdict, RiskDecision, SignalCandidate
from app.risk_engine.cost_model import CostModel
from app.risk_engine.position_sizing import compute_sizing_after_rounding


@dataclass(frozen=True)
class RiskConfig:
    risk_pct_default: float = 0.01
    max_effective_leverage: float = 3.0
    reserve_cash_pct: float = 0.20
    approval_ttl_seconds: int = 60
    max_daily_loss_pct: float = 0.03
    max_weekly_loss_pct: float = 0.06
    max_portfolio_abs_notional_usdt: float | None = None
    max_beta_adjusted_exposure_usdt: float | None = None
    min_liq_distance_pct: float = 0.05
    max_spread_bps: float = 8.0
    min_depth_usdt: float = 1_000_000
    min_net_edge_bps: float = 2.0
    config_hash: str = 'default-config'


def approve_signal(
    signal: SignalCandidate,
    ml: MLVerdict,
    account: AccountSnapshot,
    market: MarketSnapshot,
    specs: InstrumentSpec,
    cfg: RiskConfig = RiskConfig(),
    cost_model: CostModel = CostModel(),
) -> RiskDecision:
    reasons: list[str] = []
    now = utc_now()

    def fail_if(condition: bool, reason: str) -> None:
        if condition:
            reasons.append(reason)

    fail_if(not account.fresh, 'stale_account_state')
    fail_if(not market.fresh, 'stale_orderbook')
    fail_if(signal.symbol.upper() != market.symbol.upper() or signal.symbol.upper() != specs.symbol.upper(), 'symbol_runtime_mismatch')
    fail_if(not specs.fresh or specs.category != 'linear' or specs.status != 'Trading', 'bad_instrument_specs')
    # Сигнал не может попасть в sizing без stop, invalidator, evidence и feature_hash.
    fail_if(signal.stop_price is None or not signal.invalidator, 'missing_stop_or_invalidator')
    fail_if(not signal.feature_hash, 'missing_feature_hash')
    fail_if(not signal.evidence and not signal.shadow_only, 'missing_strategy_evidence')
    fail_if(signal.entry_price <= 0, 'invalid_entry_price')
    fail_if(signal.expected_gross_edge_bps <= 0, 'missing_or_nonpositive_gross_edge')
    if signal.stop_price is not None:
        fail_if(signal.stop_price <= 0 or signal.stop_price == signal.entry_price, 'invalid_stop_price')
        if signal.side.value == 'BUY':
            fail_if(signal.stop_price >= signal.entry_price, 'invalid_buy_stop_direction')
        else:
            fail_if(signal.stop_price <= signal.entry_price, 'invalid_sell_stop_direction')
    fail_if(signal.shadow_only, 'strategy_shadow_only')
    fail_if(market.spread_bps > cfg.max_spread_bps, 'spread_too_wide')
    fail_if(market.depth_usdt < cfg.min_depth_usdt, 'depth_too_low')
    fail_if(account.position_mismatch, 'position_mismatch')
    fail_if(account.daily_loss_hit or account.weekly_loss_hit, 'loss_limit_hit')
    daily_remaining_risk = account.equity_usdt * cfg.max_daily_loss_pct - account.realized_negative_today_usdt
    weekly_remaining_risk = account.equity_usdt * cfg.max_weekly_loss_pct - account.realized_negative_week_usdt
    fail_if(daily_remaining_risk <= 0, 'daily_remaining_risk_exhausted')
    fail_if(weekly_remaining_risk <= 0, 'weekly_remaining_risk_exhausted')
    fail_if(ml.required and ml.block, f'ml_block:{ml.reason or ml.verdict.value}')
    fail_if(ml.required and ml.verdict.value == 'UNAVAILABLE', 'ml_unavailable_fail_closed')

    sizing = compute_sizing_after_rounding(
        signal=signal,
        account=account,
        market=market,
        specs=specs,
        risk_pct=cfg.risk_pct_default,
        max_effective_leverage=cfg.max_effective_leverage,
        reserve_cash_pct=cfg.reserve_cash_pct,
        min_liq_distance_pct=cfg.min_liq_distance_pct,
        cost_model=cost_model,
    )

    fail_if(sizing.qty < specs.min_qty or sizing.notional < specs.min_notional, 'min_qty_or_notional')
    fail_if(sizing.max_loss_if_stop > sizing.risk_budget, 'risk_budget_exceeded')
    fail_if(sizing.max_loss_if_stop > daily_remaining_risk, 'daily_remaining_risk_exceeded')
    fail_if(sizing.max_loss_if_stop > weekly_remaining_risk, 'weekly_remaining_risk_exceeded')
    fail_if(sizing.effective_leverage > cfg.max_effective_leverage, 'leverage_cap')
    if cfg.max_portfolio_abs_notional_usdt is not None:
        fail_if(account.portfolio_abs_notional_usdt + sizing.notional > cfg.max_portfolio_abs_notional_usdt, 'portfolio_abs_exposure_cap')
    if cfg.max_beta_adjusted_exposure_usdt is not None:
        fail_if(abs(account.beta_adjusted_exposure_usdt) + sizing.notional > cfg.max_beta_adjusted_exposure_usdt, 'beta_adjusted_exposure_cap')
    fail_if(sizing.reserve_cash_after_pct < cfg.reserve_cash_pct, 'reserve_cash_violation')
    fail_if(sizing.liquidation_distance_pct < max(cfg.min_liq_distance_pct, 2.5 * sizing.stop_distance_pct), 'liq_distance_too_close')
    fail_if(sizing.expected_net_edge_bps <= cfg.min_net_edge_bps, 'no_net_edge_after_costs')

    return RiskDecision(
        risk_decision_id=str(uuid4()),
        signal_id=signal.signal_id,
        approved=not reasons,
        reasons=reasons,
        sizing=sizing,
        limits_snapshot={
            'risk_pct_default': cfg.risk_pct_default,
            'max_effective_leverage': cfg.max_effective_leverage,
            'reserve_cash_pct': cfg.reserve_cash_pct,
            'max_daily_loss_pct': cfg.max_daily_loss_pct,
            'max_weekly_loss_pct': cfg.max_weekly_loss_pct,
            'daily_remaining_risk': daily_remaining_risk,
            'weekly_remaining_risk': weekly_remaining_risk,
            'max_portfolio_abs_notional_usdt': cfg.max_portfolio_abs_notional_usdt,
            'max_beta_adjusted_exposure_usdt': cfg.max_beta_adjusted_exposure_usdt,
            'min_liq_distance_pct': cfg.min_liq_distance_pct,
            'min_net_edge_bps': cfg.min_net_edge_bps,
        },
        account_snapshot=account.model_dump(mode='json'),
        specs_version=specs.specs_version,
        feature_hash=signal.feature_hash,
        config_hash=cfg.config_hash,
        trace_id=signal.trace_id,
        created_at=now,
        expires_at=now + timedelta(seconds=cfg.approval_ttl_seconds),
    )

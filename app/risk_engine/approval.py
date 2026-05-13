from __future__ import annotations
from dataclasses import dataclass
import math
from datetime import timedelta
from uuid import uuid4
from app.core.time import utc_now
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, MLVerdict, RiskDecision, SignalCandidate
from app.risk_engine.cost_model import CostModel
from app.risk_engine.position_sizing import compute_sizing_after_rounding

SHADOW_ONLY_STRATEGIES_PHASE_0_1 = {
    'carry', 'carry_live', 'funding', 'funding_carry',
    'pair_statarb', 'statarb', 'statarb_live', 'stat_arb',
}
FORBIDDEN_PRODUCT_STRATEGIES = {'martingale', 'dca', 'spot_grid', 'inverse_futures', 'options', 'copy_trading', 'signal_bot'}


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

    # Numeric sanity checks are explicit because Python float NaN/inf can otherwise
    # slip through comparisons such as `nan <= 0` and make a dangerous candidate
    # look acceptable. Любое non-finite значение в candidate/config/cost model
    # переводит risk approval в fail-closed rejected.
    signal_numbers = (signal.entry_price, signal.expected_gross_edge_bps)
    if signal.stop_price is not None:
        signal_numbers = (*signal_numbers, signal.stop_price)
    fail_if(any(not math.isfinite(float(x)) for x in signal_numbers), 'invalid_signal_numeric_value')

    cfg_numbers = (
        cfg.risk_pct_default, cfg.max_effective_leverage, cfg.reserve_cash_pct,
        cfg.max_daily_loss_pct, cfg.max_weekly_loss_pct, cfg.min_liq_distance_pct,
        cfg.max_spread_bps, cfg.min_depth_usdt, cfg.min_net_edge_bps,
    )
    fail_if(
        any(not math.isfinite(float(x)) for x in cfg_numbers)
        or cfg.risk_pct_default <= 0
        or cfg.max_effective_leverage <= 0
        or cfg.reserve_cash_pct < 0
        or cfg.max_daily_loss_pct < 0
        or cfg.max_weekly_loss_pct < 0
        or cfg.min_liq_distance_pct < 0
        or cfg.max_spread_bps < 0
        or cfg.min_depth_usdt < 0
        or cfg.min_net_edge_bps < 0,
        'invalid_risk_config',
    )
    cost_numbers = (
        cost_model.maker_fee_bps, cost_model.taker_fee_bps, cost_model.slippage_buffer_bps,
        cost_model.funding_buffer_bps, cost_model.safety_buffer_bps,
    )
    fail_if(
        any(not math.isfinite(float(x)) for x in cost_numbers) or any(float(x) < 0 for x in cost_numbers),
        'invalid_cost_model',
    )

    fail_if(not account.fresh, 'stale_account_state')
    fail_if(not market.fresh, 'stale_orderbook')
    fail_if(not market.funding_fresh, 'stale_funding')
    fail_if(signal.symbol.upper() != market.symbol.upper() or signal.symbol.upper() != specs.symbol.upper(), 'symbol_runtime_mismatch')
    fail_if(not specs.fresh or specs.category != 'linear' or specs.status != 'Trading', 'bad_instrument_specs')
    numeric_specs = (specs.tick_size, specs.qty_step, specs.min_qty, specs.min_notional, specs.max_leverage)
    fail_if(
        any(not math.isfinite(float(x)) for x in numeric_specs)
        or specs.tick_size <= 0
        or specs.qty_step <= 0
        or specs.min_qty <= 0
        or specs.min_notional <= 0
        or specs.max_leverage <= 0,
        'invalid_instrument_specs',
    )
    fail_if(
        any(not math.isfinite(float(x)) for x in (market.bid1, market.ask1, market.spread_bps, market.depth_usdt, market.funding_bps))
        or market.bid1 <= 0
        or market.ask1 <= 0
        or market.ask1 < market.bid1
        or market.spread_bps < 0
        or market.depth_usdt < 0,
        'invalid_market_snapshot',
    )
    fail_if(not math.isfinite(float(account.equity_usdt)) or account.equity_usdt <= 0, 'invalid_account_equity')
    fail_if(not math.isfinite(float(account.available_balance_usdt)) or account.available_balance_usdt < 0, 'invalid_account_balance')
    # Сигнал не может попасть в sizing без stop, invalidator, evidence и feature_hash.
    fail_if(signal.stop_price is None or not signal.invalidator, 'missing_stop_or_invalidator')
    fail_if(not signal.feature_hash, 'missing_feature_hash')
    fail_if(not signal.regime_id or not signal.feature_id or not signal.required_data, 'incomplete_signal_lineage')
    fail_if(not signal.evidence and not signal.shadow_only, 'missing_strategy_evidence')
    fail_if(signal.entry_price <= 0, 'invalid_entry_price')
    fail_if(signal.expected_gross_edge_bps <= 0, 'missing_or_nonpositive_gross_edge')
    if signal.stop_price is not None:
        fail_if(signal.stop_price <= 0 or signal.stop_price == signal.entry_price, 'invalid_stop_price')
        if signal.side.value == 'BUY':
            fail_if(signal.stop_price >= signal.entry_price, 'invalid_buy_stop_direction')
        else:
            fail_if(signal.stop_price <= signal.entry_price, 'invalid_sell_stop_direction')
    strategy_name = signal.strategy.lower()
    fail_if(strategy_name in FORBIDDEN_PRODUCT_STRATEGIES, 'strategy_forbidden_product_scope')
    fail_if(signal.shadow_only or (account.phase <= 1 and strategy_name in SHADOW_ONLY_STRATEGIES_PHASE_0_1), 'strategy_shadow_only')
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

    try:
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
    except Exception as exc:
        # Ошибка sizing не должна превращаться в 500 или в advisory-pass.
        # Любая невалидная биржевая спецификация/математика fail-closed.
        reasons.append(f'sizing_failed:{type(exc).__name__}')
        from app.schemas.domain import SizingResult
        sizing = SizingResult(risk_budget=max(account.equity_usdt * cfg.risk_pct_default, 0.0))

    fail_if(sizing.qty < specs.min_qty or sizing.notional < specs.min_notional, 'min_qty_or_notional')
    fail_if(sizing.max_loss_if_stop > sizing.risk_budget, 'risk_budget_exceeded')
    fail_if(sizing.max_loss_if_stop > daily_remaining_risk, 'daily_remaining_risk_exceeded')
    fail_if(sizing.max_loss_if_stop > weekly_remaining_risk, 'weekly_remaining_risk_exceeded')
    fail_if(sizing.effective_leverage > cfg.max_effective_leverage, 'leverage_cap')
    portfolio_abs_after = account.portfolio_abs_notional_usdt + sizing.notional
    # Даже если отдельный абсолютный portfolio cap не задан в YAML, max effective
    # leverage остается hard cap для суммарной экспозиции портфеля.
    fail_if(portfolio_abs_after / max(account.equity_usdt, 1e-9) > cfg.max_effective_leverage, 'leverage_cap')
    if cfg.max_portfolio_abs_notional_usdt is not None:
        fail_if(portfolio_abs_after > cfg.max_portfolio_abs_notional_usdt, 'portfolio_abs_exposure_cap')
    # Beta cap тоже fail-closed по умолчанию через leverage cap. Snapshot хранит
    # conservative absolute beta exposure; для Phase 0 это соответствует запрету
    # на скрытую коррелированную экспозицию.
    beta_cap = cfg.max_beta_adjusted_exposure_usdt if cfg.max_beta_adjusted_exposure_usdt is not None else account.equity_usdt * cfg.max_effective_leverage
    fail_if(abs(account.beta_adjusted_exposure_usdt) + sizing.notional > beta_cap, 'beta_adjusted_exposure_cap')
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

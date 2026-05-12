from __future__ import annotations
import math
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, SignalCandidate, SizingResult
from app.risk_engine.cost_model import CostModel


def floor_to_step(value: float, step: float) -> float:
    if step <= 0:
        raise ValueError('step must be positive')
    return math.floor(value / step) * step


def compute_sizing_after_rounding(
    signal: SignalCandidate,
    account: AccountSnapshot,
    market: MarketSnapshot,
    specs: InstrumentSpec,
    risk_pct: float,
    max_effective_leverage: float,
    reserve_cash_pct: float,
    min_liq_distance_pct: float,
    cost_model: CostModel,
) -> SizingResult:
    entry = float(signal.entry_price)
    stop = float(signal.stop_price or 0)
    stop_distance_abs = abs(entry - stop)
    if entry <= 0 or stop_distance_abs <= 0:
        return SizingResult(risk_budget=account.equity_usdt * risk_pct)

    risk_budget = account.equity_usdt * risk_pct
    qty_raw = risk_budget / stop_distance_abs
    qty = floor_to_step(qty_raw, specs.qty_step)
    notional = qty * entry
    estimated_exit_costs = notional * (cost_model.round_trip_cost_bps(market.spread_bps, taker=False, funding_bps=market.funding_bps) / 10000.0)
    max_loss_if_stop = qty * stop_distance_abs + estimated_exit_costs
    effective_leverage = notional / max(account.equity_usdt, 1e-9)
    # Резерв считается после conservative initial margin estimate. Старый вариант
    # вычитал только costs и мог пропустить позицию, которая формально укладывалась
    # в risk_usdt, но фактически съедала весь свободный баланс малого счета.
    estimated_initial_margin = notional / max(max_effective_leverage, 1e-9)
    reserve_cash_after_pct = max((account.available_balance_usdt - estimated_exit_costs - estimated_initial_margin) / max(account.equity_usdt, 1e-9), 0.0)
    stop_distance_pct = stop_distance_abs / entry
    # Conservative approximation when exchange liq price is not available.
    liquidation_distance_pct = max(1 / max(effective_leverage, 1e-9) - 0.01, 0.0) if effective_leverage > 0 else 1.0
    expected_net_edge_bps = cost_model.expected_net_edge_bps(signal.expected_gross_edge_bps, market.spread_bps, taker=False, funding_bps=market.funding_bps)

    return SizingResult(
        qty=qty,
        notional=notional,
        risk_budget=risk_budget,
        stop_distance_abs=stop_distance_abs,
        stop_distance_pct=stop_distance_pct,
        max_loss_if_stop=max_loss_if_stop,
        effective_leverage=effective_leverage,
        reserve_cash_after_pct=reserve_cash_after_pct,
        liquidation_distance_pct=liquidation_distance_pct,
        expected_net_edge_bps=expected_net_edge_bps,
    )

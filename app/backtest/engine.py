from __future__ import annotations
from dataclasses import dataclass


@dataclass
class BacktestTrade:
    gross_pnl: float
    notional: float
    spread_bps: float
    slippage_bps: float
    fee_bps: float
    funding_bps: float = 0.0


class ExecutionAwareBacktester:
    def evaluate(self, trades: list[BacktestTrade]) -> dict:
        # Отчет валиден только в net-представлении: комиссии, spread, slippage и funding вычитаются по каждой сделке.
        gross = sum(t.gross_pnl for t in trades)
        per_trade_net = []
        per_trade_costs = []
        for t in trades:
            costs = t.notional * (2*t.fee_bps + t.spread_bps + t.slippage_bps + abs(t.funding_bps)) / 10000
            per_trade_costs.append(costs)
            per_trade_net.append(t.gross_pnl - costs)
        costs_total = sum(per_trade_costs)
        net = sum(per_trade_net)
        net_wins = [x for x in per_trade_net if x > 0]
        net_losses = [x for x in per_trade_net if x < 0]
        profit_factor = (sum(net_wins) / abs(sum(net_losses))) if net_losses else (float('inf') if net_wins else 0.0)
        return {
            'trade_count': len(trades),
            'gross_pnl': gross,
            'costs': costs_total,
            'net_pnl': net,
            'gross_only_valid': False,
            'win_rate_net': len(net_wins) / len(trades) if trades else 0,
            'losses_net': len(net_losses),
            'profit_factor_net': profit_factor,
            'skipped_or_rejected_reasons_required': True,
        }

from app.backtest.engine import BacktestTrade, ExecutionAwareBacktester
from app.risk_engine.cost_model import CostModel
from app.risk_engine.position_sizing import floor_to_step


def test_cost_model_includes_funding_buffer_monotonically():
    base = CostModel(maker_fee_bps=2, slippage_buffer_bps=2, funding_buffer_bps=1, safety_buffer_bps=2)
    assert base.round_trip_cost_bps(spread_bps=1, taker=False, funding_bps=0) == 10
    higher_funding = base.round_trip_cost_bps(spread_bps=1, taker=False, funding_bps=5)
    assert higher_funding > base.round_trip_cost_bps(spread_bps=1, taker=False, funding_bps=0)


def test_backtester_reports_net_not_gross_win_rate():
    report = ExecutionAwareBacktester().evaluate([
        BacktestTrade(gross_pnl=1.0, notional=1000, spread_bps=2, slippage_bps=2, fee_bps=5),
    ])
    assert report['gross_pnl'] == 1.0
    assert report['net_pnl'] < 0
    assert report['win_rate_net'] == 0
    assert report['gross_only_valid'] is False


def test_floor_to_step_never_rounds_up_from_float_noise():
    assert floor_to_step(0.3, 0.1) == 0.3
    assert floor_to_step(0.999999999999, 0.001) == 0.999
    assert floor_to_step(1.000000000001, 0.001) == 1.0

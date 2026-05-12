from app.config.runtime import build_runtime_config


def test_runtime_config_loads_yaml_values():
    runtime = build_runtime_config()
    assert runtime.phase == 0
    assert runtime.live_universe == ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')
    assert runtime.risk.max_effective_leverage == 3.0
    assert runtime.costs.maker_fee_bps == 2.0
    assert runtime.config_hash

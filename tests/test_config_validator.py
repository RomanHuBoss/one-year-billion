import pytest
from app.config.validator import validate_config, ConfigValidationError


def test_forbidden_frontend_secrets_rejected():
    cfg = {'system.yaml': {'exchange_scope': {'category':'linear','quote':'USDT','forbid_spot':True,'forbid_inverse':True,'forbid_options':True}, 'frontend': {'store_secrets': True}}, 'account_phase.yaml': {'phase':0,'live_strategies':[]}, 'risk.yaml': {'recovery_can_increase_risk': False}}
    with pytest.raises(ConfigValidationError):
        validate_config(cfg)


def _valid_cfg(live_strategies):
    return {
        'system.yaml': {
            'exchange_scope': {'category':'linear','quote':'USDT','forbid_spot':True,'forbid_inverse':True,'forbid_options':True},
            'frontend': {'store_secrets': False},
        },
        'account_phase.yaml': {
            'phase': 0,
            'live_universe': ['BTCUSDT'],
            'live_strategies': live_strategies,
            'manual_override_reduce_only': True,
        },
        'risk.yaml': {
            'risk_pct_default': 0.01,
            'risk_pct_absolute_max': 0.015,
            'max_effective_leverage': 3.0,
            'max_effective_leverage_absolute': 5.0,
            'min_net_edge_bps': 2.0,
            'recovery_can_increase_risk': False,
        },
    }


def test_forbidden_strategy_names_are_case_insensitive():
    with pytest.raises(ConfigValidationError, match='forbidden_strategy_in_live_permissions'):
        validate_config(_valid_cfg(['DCA']))


def test_negative_cost_or_liquidity_parameters_are_rejected():
    cfg = _valid_cfg(['breakout'])
    cfg['risk.yaml']['slippage_buffer_bps'] = -0.01
    with pytest.raises(ConfigValidationError, match='slippage_buffer_bps_must_be_nonnegative'):
        validate_config(cfg)


@pytest.mark.parametrize(
    ('field', 'value', 'reason'),
    [
        ('risk_pct_default', 0.016, 'phase0_risk_default_above_1_5pct'),
        ('risk_pct_absolute_max', 0.02, 'phase0_risk_absolute_above_1_5pct'),
        ('max_effective_leverage', 3.1, 'phase0_default_leverage_above_3x'),
        ('max_effective_leverage_absolute', 5.1, 'phase0_absolute_leverage_above_5x'),
        ('turnover_round_turns_per_day', 5, 'phase0_turnover_above_4_round_turns_per_day'),
    ],
)
def test_phase0_hard_caps_are_enforced_by_config_validator(field, value, reason):
    cfg = _valid_cfg(['breakout'])
    cfg['risk.yaml'][field] = value
    with pytest.raises(ConfigValidationError, match=reason):
        validate_config(cfg)

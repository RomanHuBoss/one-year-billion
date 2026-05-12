import pytest
from app.config.phase_validator import validate_strategy_for_phase
from app.config.validator import validate_config, ConfigValidationError
from tests.test_config_validator import _valid_cfg


@pytest.mark.parametrize('strategy', ['copy_trading', 'signal_bot', 'portfolio_bot'])
def test_product_scope_forbidden_strategies_blocked_in_config(strategy):
    with pytest.raises(ConfigValidationError, match='forbidden_strategy_in_live_permissions'):
        validate_config(_valid_cfg([strategy]))


@pytest.mark.parametrize('strategy', ['copy_trading', 'signal_bot', 'portfolio_bot'])
def test_product_scope_forbidden_strategies_blocked_by_phase_validator(strategy):
    check = validate_strategy_for_phase(strategy, 0, ('breakout', 'micro_grid'), ())
    assert not check.allowed
    assert 'strategy_forbidden_product_scope' in check.reasons


@pytest.mark.parametrize('strategy', ['funding', 'funding_carry', 'statarb', 'stat_arb'])
def test_phase0_1_shadow_funding_statarb_aliases_have_no_live_route(strategy):
    check = validate_strategy_for_phase(strategy, 1, ('breakout', 'micro_grid'), ('carry_shadow', 'statarb_shadow'))
    assert not check.allowed
    assert 'strategy_shadow_only_phase_0_1' in check.reasons

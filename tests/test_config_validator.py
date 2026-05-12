import pytest
from app.config.validator import validate_config, ConfigValidationError


def test_forbidden_frontend_secrets_rejected():
    cfg = {'system.yaml': {'exchange_scope': {'category':'linear','quote':'USDT','forbid_spot':True,'forbid_inverse':True,'forbid_options':True}, 'frontend': {'store_secrets': True}}, 'account_phase.yaml': {'phase':0,'live_strategies':[]}, 'risk.yaml': {'recovery_can_increase_risk': False}}
    with pytest.raises(ConfigValidationError):
        validate_config(cfg)

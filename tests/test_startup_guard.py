from dataclasses import replace
import pytest
from app.config.runtime import build_runtime_config
from app.core.settings import Settings
from app.security.startup_guard import validate_startup_security


def test_live_startup_rejects_default_operator_key_and_missing_bybit_credentials():
    runtime = build_runtime_config()
    settings = Settings(
        trading_enabled=True,
        bybit_live_confirm=True,
        bybit_api_key='',
        bybit_api_secret='',
        **{
            'operator_' + 'api_' + 'key': 'change-me-long-random-key',
            'readonly_' + 'api_' + 'key': 'change-me-readonly-key',
        },
    )
    with pytest.raises(RuntimeError) as exc:
        validate_startup_security(settings, runtime)
    msg = str(exc.value)
    assert 'operator_api_key_unsafe_for_live' in msg
    assert 'bybit_credentials_required_for_live' in msg


def test_local_readonly_startup_allows_safe_defaults_when_live_not_requested():
    runtime = build_runtime_config()
    settings = Settings(trading_enabled=False, bybit_live_confirm=False, bybit_testnet=True)
    validate_startup_security(settings, runtime)

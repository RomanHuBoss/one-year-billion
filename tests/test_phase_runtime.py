from fastapi.testclient import TestClient
import pytest
from app.config.phase_validator import validate_symbol_for_phase, validate_strategy_for_phase
from app.main import app


def test_phase0_rejects_unapproved_symbol():
    check = validate_symbol_for_phase('BNBUSDT', 0, ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'))
    assert not check.allowed
    assert 'symbol_not_in_config_live_universe' in check.reasons


def test_phase0_carry_live_has_no_route():
    check = validate_strategy_for_phase('carry_live', 0, ('breakout', 'micro_grid'), ('carry_shadow',))
    assert not check.allowed
    assert 'strategy_shadow_only_phase_0_1' in check.reasons


def test_runtime_preflight_exposes_config_hash_and_safe_scope():
    client = TestClient(app)
    response = client.get('/api/runtime/preflight', headers={'x-api-key': app.state.settings.readonly_api_key})
    assert response.status_code == 200
    payload = response.json()
    assert payload['data']['exchange_scope'] == 'bybit_v5_linear_usdt_only'
    assert payload['data']['live_order_submit_enabled'] is False
    assert payload['data']['frontend_source_of_truth'] == 'backend_status_effective'
    assert payload['data']['config_hash']

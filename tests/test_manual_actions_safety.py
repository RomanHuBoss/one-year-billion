from fastapi.testclient import TestClient
from app.main import app


def test_config_activation_requires_risk_reducing_metadata():
    client = TestClient(app)
    headers = {'x-api-key': app.state.settings.operator_api_key, 'X-Idempotency-Key': 'cfg-risk-up'}
    response = client.post('/api/actions', json={
        'action': 'ACTIVATE_CONFIG',
        'reason': 'проверка запрета risk-up override',
        'target': {'config_hash': 'abc', 'risk_increase': True},
    }, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'rejected'
    assert 'config_change_must_be_risk_reducing_or_neutral' in payload['reasons']
    assert 'config_risk_increase_forbidden' in payload['reasons']


def test_config_activation_allows_neutral_or_risk_decrease_only():
    client = TestClient(app)
    headers = {'x-api-key': app.state.settings.operator_api_key, 'X-Idempotency-Key': 'cfg-risk-decrease'}
    response = client.post('/api/actions', json={
        'action': 'ACTIVATE_CONFIG',
        'reason': 'понижение риска после incident review',
        'target': {'config_hash': 'abc', 'risk_change': 'decrease'},
    }, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['data']['reduce_only'] is True

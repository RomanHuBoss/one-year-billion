from fastapi.testclient import TestClient
from app.main import app


def _read_headers():
    return {'x-api-key': app.state.settings.readonly_api_key}


def _operator_headers(key='workflow-test'):
    return {'x-api-key': app.state.settings.operator_api_key, 'X-Idempotency-Key': key}


def test_operator_workflow_endpoint_returns_sequential_gates():
    client = TestClient(app)
    response = client.get('/api/operator/workflow', headers=_read_headers())
    assert response.status_code == 200
    data = response.json()['data']
    assert data['source_of_truth'] == 'backend_operator_workflow'
    ids = [step['id'] for step in data['steps']]
    assert ids == ['db', 'validate', 'testnet_preflight', 'paper_shadow', 'security', 'reconciliation', 'go_no_go', 'live_preflight']
    assert all('substeps' in step and isinstance(step['substeps'], list) for step in data['steps'])
    assert 'Нет approved non-expired risk_decision_id -> нет order' in data['invariants']


def test_operator_workflow_action_requires_operator_key_and_reason():
    client = TestClient(app)
    rejected = client.post(
        '/api/operator/workflow/actions/run_validate',
        headers={'X-Idempotency-Key': 'workflow-no-key'},
        json={'reason': 'pytest'},
    )
    assert rejected.status_code == 403


def test_frontend_contains_workflow_wizard_not_console_runbook():
    html = open('frontend/index.html', encoding='utf-8').read()
    js = open('frontend/js/app.js', encoding='utf-8').read()
    assert 'Крупные вехи запуска' in html
    assert 'Выполнить следующий доступный шаг' in html
    assert '/api/operator/workflow' in js
    assert '/api/operator/workflow/actions/' in js
    assert 'PHASE0_PAPER PASS после 14+ дней' not in js  # frontend не хардкодит gate logic, получает ее с backend

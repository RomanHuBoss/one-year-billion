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


def test_workflow_db_step_turns_ok_after_lazy_schema_refresh(monkeypatch):
    from app.api.routes import operator_workflow

    class FakeRepo:
        def evidence_summary(self, _config_hash):
            return {t: None for t in operator_workflow.EVIDENCE_TYPES}

    old_repo = getattr(app.state, 'repository', None)
    old_db_available = getattr(app.state, 'db_available', False)
    old_db_schema_ready = getattr(app.state, 'db_schema_ready', False)
    try:
        app.state.repository = FakeRepo()
        app.state.db_available = False
        app.state.db_schema_ready = False

        def fake_ensure(_app):
            _app.state.repository = FakeRepo()
            _app.state.db_available = True
            _app.state.db_schema_ready = True
            _app.state.db_missing_tables = []
            return {'connection_ok': True, 'schema_ready': True, 'missing_tables': [], 'error': None}

        monkeypatch.setattr(operator_workflow, 'ensure_database_ready', fake_ensure)
        client = TestClient(app)
        response = client.get('/api/operator/workflow', headers=_read_headers())
        assert response.status_code == 200
        data = response.json()['data']
        db_step = next(step for step in data['steps'] if step['id'] == 'db')
        assert db_step['status'] == 'ok'
        assert db_step['blocks_next'] is False
        assert data['database_available'] is True
        assert data['database_schema_ready'] is True
    finally:
        app.state.repository = old_repo
        app.state.db_available = old_db_available
        app.state.db_schema_ready = old_db_schema_ready


def test_frontend_job_result_surfaces_operator_hints_for_bybit_time_window():
    js = open('frontend/js/app.js', encoding='utf-8').read()
    css = open('frontend/css/styles.css', encoding='utf-8').read()
    help_js = open('frontend/js/context_help.js', encoding='utf-8').read()
    assert 'renderJobOperatorHints' in js
    assert 'bybit_timestamp_window_error' in js
    assert 'это timestamp/recv_window gate Bybit' in js
    assert 'job-hints' in css
    assert 'bybit_timestamp_window_error_10002' in help_js

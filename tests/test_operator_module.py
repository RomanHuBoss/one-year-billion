from fastapi.testclient import TestClient
from app.main import app

def _operator_key():
    return app.state.settings.operator_api_key


def test_operator_dashboard_returns_human_readable_operator_model():
    client = TestClient(app)
    response = client.get('/api/operator/dashboard')
    assert response.status_code == 200
    payload = response.json()
    data = payload['data']
    assert data['source_of_truth'] == 'backend_status_effective'
    assert data['hero']['title']
    assert data['cards']
    assert data['steps']
    assert data['symbols']
    assert data['safe_actions']
    assert data['limits']['phase'] == 0
    assert 'BTCUSDT' in data['limits']['universe']
    assert all('status_label' in row and 'operator_hint' in row for row in data['symbols'])


def test_operator_frontend_is_not_raw_json_dashboard():
    html = open('frontend/index.html', encoding='utf-8').read()
    css = open('frontend/css/styles.css', encoding='utf-8').read()
    js = open('frontend/js/app.js', encoding='utf-8').read()
    assert 'Операторский модуль' in html
    assert 'Панель допуска' in html
    assert 'Что мешает запуску' in html
    assert 'Безопасные действия оператора' in html
    assert 'cards-grid' in css
    assert '/api/operator/dashboard' in js
    assert 'status_effective' in html
    assert '<pre id="health"' not in html
    assert '<pre id="risk"' not in html
    assert '<pre id="ml"' not in html
    assert '<pre id="runtime"' not in html




def test_paper_summary_does_not_derive_status_from_frontend_risk_approval():
    client = TestClient(app)
    response = client.post('/api/paper/run-once')
    assert response.status_code == 200
    decisions = response.json()['data']['decisions']
    assert decisions
    assert all('status' in row for row in decisions)

    app_js = open('frontend/js/app.js', encoding='utf-8').read()
    assert 'row.risk?.approved' not in app_js
    assert 'row.risk.approved' not in app_js
    assert "? 'risk_approved'" not in app_js
    assert '? "risk_approved"' not in app_js
    assert 'status_from_backend_missing' in app_js

def test_operator_frontend_has_context_help_on_right_click():
    html = open('frontend/index.html', encoding='utf-8').read()
    js = open('frontend/js/app.js', encoding='utf-8').read()
    help_js = open('frontend/js/context_help.js', encoding='utf-8').read()
    css = open('frontend/css/styles.css', encoding='utf-8').read()
    assert 'globalHelpBtn' in html
    assert 'Правая кнопка по любому блоку' in html
    assert 'data-help="hero"' in html
    assert 'data-help="actions"' in html
    assert "installContextHelp" in js
    assert "contextmenu" in help_js
    assert 'Вызвать справку' in help_js
    assert 'help-dialog' in css
    assert 'stale_market' in help_js
    assert 'Нет approved non-expired risk_decision_id' in help_js


def test_operator_dashboard_exposes_allowlisted_python_commands():
    client = TestClient(app)
    response = client.get('/api/operator/dashboard')
    assert response.status_code == 200
    data = response.json()['data']
    command_ids = {cmd['command_id'] for cmd in data['operator_commands']}
    assert {'validate', 'preflight_testnet', 'bootstrap_db', 'preflight_live'} <= command_ids
    postgresql_step = next(step for step in data['steps'] if step['id'] == 'postgresql')
    assert postgresql_step['command'] == 'python scripts/bootstrap_db.py'
    assert './scripts/bootstrap_db.sh' not in open('frontend/index.html', encoding='utf-8').read()


def test_operator_commands_endpoint_is_allowlist_and_write_requires_operator_key():
    client = TestClient(app)
    listed = client.get('/api/operator/commands')
    assert listed.status_code == 200
    commands = listed.json()['data']['commands']
    assert all('command_id' in item and 'safety' in item for item in commands)

    rejected = client.post(
        '/api/operator/commands/preflight_testnet/run',
        headers={'X-Idempotency-Key': 'cmd-test-no-key'},
        json={'reason': 'pytest should require operator key', 'options': {}},
    )
    assert rejected.status_code == 403

    accepted = client.post(
        '/api/operator/commands/preflight_testnet/run',
        headers={'x-api-key': _operator_key(), 'X-Idempotency-Key': 'cmd-test-preflight'},
        json={'reason': 'pytest проверяет allowlisted command runner', 'options': {}},
    )
    assert accepted.status_code == 200
    payload = accepted.json()
    assert payload['status'] == 'accepted'
    job = payload['data']['job']
    assert job['command_id'] == 'preflight_testnet'
    assert job['command_display'] == 'python main.py preflight --mode testnet'

    blocked = client.post(
        '/api/operator/commands/rm_rf/run',
        headers={'x-api-key': _operator_key(), 'X-Idempotency-Key': 'cmd-test-forbidden'},
        json={'reason': 'pytest checks forbidden arbitrary command', 'options': {}},
    )
    assert blocked.status_code == 404


def test_python_bootstrap_db_replaces_shell_bootstrap_for_ui():
    assert open('scripts/bootstrap_db.py', encoding='utf-8').read().find('apply_migrations') >= 0
    app_js = open('frontend/js/app.js', encoding='utf-8').read()
    html = open('frontend/index.html', encoding='utf-8').read()
    help_js = open('frontend/js/context_help.js', encoding='utf-8').read()
    assert '/api/operator/commands/' in app_js
    assert 'Операционный центр' in html
    assert 'python scripts/bootstrap_db.py' in help_js
    assert 'shell=False' in open('app/services/operator_jobs.py', encoding='utf-8').read()


def test_operator_command_accepts_browser_text_plain_json_body_after_header_bug():
    client = TestClient(app)
    accepted = client.post(
        '/api/operator/commands/preflight_testnet/run',
        headers={'x-api-key': _operator_key(), 'X-Idempotency-Key': 'cmd-test-text-body'},
        data='{"reason":"Первичная проверка проекта","options":{}}',
    )
    assert accepted.status_code == 200, accepted.text
    payload = accepted.json()
    assert payload['status'] == 'accepted'
    assert payload['data']['job']['command_id'] == 'preflight_testnet'


def test_api_client_preserves_content_type_when_custom_headers_are_added():
    api_client = open('frontend/js/api_client.js', encoding='utf-8').read()
    assert 'const { headers: optionHeaders = {}, ...requestOptions } = options;' in api_client
    assert '...requestOptions,' in api_client
    assert "'Content-Type': 'application/json'" in api_client
    assert '...optionHeaders' in api_client
    assert "headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },\n    ...options" not in api_client


def test_operator_job_status_does_not_hide_traceback_or_blocked_json():
    runner = app.state.operator_jobs
    assert runner._derive_status(0, '{"status":"blocked","reasons":["x"]}', '') == 'blocked'
    assert runner._derive_status(0, '', 'Traceback (most recent call last):\nboom') == 'error'
    assert runner._derive_status(1, 'pytest output', '') == 'blocked'


def test_live_preflight_missing_schema_returns_blocked_not_traceback():
    from app.live.preflight import run_live_preflight

    class BrokenRepository:
        def unresolved_critical_high(self):
            raise RuntimeError('relation "incidents" does not exist')

        def live_evidence_status(self, *_args):
            raise RuntimeError('relation "go_no_go_evidence" does not exist')

    result = run_live_preflight(
        settings=app.state.settings,
        runtime=app.state.runtime_config,
        db_available=True,
        repository=BrokenRepository(),
    )
    assert result.status == 'blocked'
    assert 'incidents_table_missing_or_migrations_not_applied' in result.reasons
    assert 'go_no_go_tables_missing_or_migrations_not_applied' in result.reasons
    assert 'unresolved_critical_high_error' in result.data


def test_operator_frontend_supports_readonly_api_key_for_protected_dashboard():
    html = open('frontend/index.html', encoding='utf-8').read()
    js = open('frontend/js/app.js', encoding='utf-8').read()
    client_js = open('frontend/js/api_client.js', encoding='utf-8').read()

    assert 'readonlyApiKey' in html
    assert 'READONLY_API_KEY' in html
    assert 'saveReadonlyKeyBtn' in html
    assert 'clearReadonlyKeyBtn' in html
    assert "sessionStorage.setItem(READONLY_KEY_STORAGE" in client_js
    assert "headers['x-api-key'] = readKey" in client_js
    assert 'Укажите READONLY_API_KEY' in client_js
    assert 'getReadApiKey' in js
    assert 'setReadApiKey' in js
    assert 'initReadonlyKeyControls' in js


def test_cli_testnet_serve_uses_testnet_app_env_not_local_smoke():
    main_py = open('main.py', encoding='utf-8').read()
    assert "elif args.mode == 'testnet':" in main_py
    assert "os.environ['APP_ENV'] = 'testnet'" in main_py
    assert "os.environ['APP_ENV'] = 'local'\n    elif args.mode == 'live'" not in main_py

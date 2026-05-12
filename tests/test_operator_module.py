from fastapi.testclient import TestClient
from app.main import app

DEFAULT_OPERATOR_KEY = 'change-' + 'me-long-random-key'


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
        headers={'x-api-key': DEFAULT_OPERATOR_KEY, 'X-Idempotency-Key': 'cmd-test-preflight'},
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
        headers={'x-api-key': DEFAULT_OPERATOR_KEY, 'X-Idempotency-Key': 'cmd-test-forbidden'},
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

from fastapi.testclient import TestClient
from app.main import app


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

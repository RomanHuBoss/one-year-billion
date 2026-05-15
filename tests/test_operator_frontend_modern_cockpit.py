from html.parser import HTMLParser
from pathlib import Path


class IdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.classes = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id':
                self.ids.add(value)
            if key == 'class' and value:
                self.classes.extend(value.split())


def _read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_operator_cockpit_has_modern_sections_and_required_dom_ids():
    html = _read('frontend/index.html')
    parser = IdParser()
    parser.feed(html)

    required_ids = {
        'hero', 'heroTitle', 'heroMessage', 'nextStep', 'metricPass', 'metricLocked', 'metricBlocked',
        'cardsGrid', 'workflowSummary', 'workflowSteps', 'blockersList', 'nextActions', 'commandMatrix',
        'symbols', 'symbolDetails', 'safeActionsList', 'invariants', 'actionResult', 'diagnosticJson',
        'workflowReason', 'workflowApprovedBy', 'topApiKey', 'refreshBtn', 'runNextBtn', 'globalHelpBtn',
    }
    assert required_ids <= parser.ids
    assert {'hero-card', 'action-cockpit', 'cards-grid', 'workflow-steps', 'symbol-list'} <= set(parser.classes)
    assert '/api/actions' in html
    assert 'Панель допуска' in html
    assert 'Что мешает запуску' in html
    assert 'Безопасные действия оператора' in html
    assert 'Правая кнопка по любому блоку' in html


def test_operator_actions_use_in_page_audit_fields_not_browser_prompts():
    js = _read('frontend/js/app.js')
    assert 'workflowReason' in js
    assert 'workflowApprovedBy' in js
    assert 'prompt(' not in js
    assert '/api/operator/workflow/actions/' in js
    assert '/api/actions' in js
    assert 'safe-action-run' in js
    assert 'X-Idempotency-Key' in js


def test_operator_cockpit_css_keeps_responsive_modern_layout():
    css = _read('frontend/css/styles.css')
    assert 'backdrop-filter' in css
    assert 'grid-template-columns: repeat(6' in css
    assert '.safe-action-card .btn' in css
    assert '.action-cockpit' in css
    assert '.workflow-step.current' in css
    assert '@media (max-width: 1280px)' in css
    assert '@media (max-width: 860px)' in css
    assert ':focus-visible' in css



def test_operator_frontend_has_no_browser_storage_or_direct_exchange_calls():
    html = _read('frontend/index.html')
    js_files = [
        'frontend/js/app.js',
        'frontend/js/api_client.js',
        'frontend/js/context_help.js',
        'frontend/js/status_contract.js',
    ]
    combined = html + '\n' + '\n'.join(_read(path) for path in js_files)
    forbidden = [
        'localStorage',
        'sessionStorage',
        'api.bybit.com',
        'api-testnet.bybit.com',
        '/v5/order/create',
        '/v5/position',
        'BYBIT_API_SECRET',
    ]
    for token in forbidden:
        assert token not in combined
    assert 'OPERATOR_API_KEY / READONLY_API_KEY' in html
    assert 'Не вводите сюда Bybit API key' in html


def test_operator_frontend_result_renders_request_trace_server_time_and_reasons():
    js = _read('frontend/js/app.js')
    css = _read('frontend/css/styles.css')
    assert 'renderEnvelopeMeta' in js
    assert 'request_id:' in js
    assert 'trace_id:' in js
    assert 'server_time:' in js
    assert 'Reasons:' in js
    assert 'Backend-результат действия' in js
    assert 'result-meta' in css


def test_operator_frontend_contains_no_risk_up_or_manual_trade_controls():
    html = _read('frontend/index.html').lower()
    js = _read('frontend/js/app.js').lower()
    combined = html + '\n' + js
    forbidden_phrases = [
        'открыть сделку',
        'увеличить плечо',
        'повысить риск',
        'обойти risk engine',
        'force order',
        'increase leverage',
        'open trade',
    ]
    for phrase in forbidden_phrases:
        assert phrase not in combined
    assert '/api/actions' in combined
    assert 'safe-action-run' in combined
    assert 'risk_direction' in combined

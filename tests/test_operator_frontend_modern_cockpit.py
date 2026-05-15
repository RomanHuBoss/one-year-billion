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
    assert 'X-Idempotency-Key' in js


def test_operator_cockpit_css_keeps_responsive_modern_layout():
    css = _read('frontend/css/styles.css')
    assert 'backdrop-filter' in css
    assert 'grid-template-columns: repeat(6' in css
    assert '.action-cockpit' in css
    assert '.workflow-step.current' in css
    assert '@media (max-width: 1280px)' in css
    assert '@media (max-width: 860px)' in css
    assert ':focus-visible' in css

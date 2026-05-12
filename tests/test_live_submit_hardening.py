from datetime import timedelta
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.core.time import utc_now
from app.execution.idempotency import InMemoryIdempotencyStore
from app.execution.order_router import OrderRouter
from app.main import app


def _payload():
    now = utc_now()
    return {
        'idempotency_key': 'idem-live-repeat',
        'signal': {
            'signal_id': '00000000-0000-0000-0000-000000000101',
            'strategy': 'micro_grid',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 100000,
            'stop_price': 99000,
            'invalidator': 'range_break',
            'expected_gross_edge_bps': 30,
            'trace_id': 't-live-repeat',
            'strategy_version': '1',
            'feature_hash': 'fh-live-repeat',
            'evidence': {'range_quality': 'ok'},
        },
        'risk_decision': {
            'risk_decision_id': '00000000-0000-0000-0000-000000000102',
            'signal_id': '00000000-0000-0000-0000-000000000101',
            'approved': True,
            'reasons': [],
            'sizing': {
                'qty': 0.001,
                'notional': 100,
                'risk_budget': 5,
                'stop_distance_abs': 1000,
                'stop_distance_pct': 0.01,
                'max_loss_if_stop': 2,
                'expected_net_edge_bps': 10,
            },
            'limits_snapshot': {},
            'account_snapshot': {},
            'specs_version': 'runtime-v1',
            'feature_hash': 'fh-live-repeat',
            'config_hash': 'cfg',
            'trace_id': 't-live-repeat',
            'created_at': now.isoformat(),
            'expires_at': (now + timedelta(seconds=60)).isoformat(),
        },
    }


class FakeRepo:
    def __init__(self):
        self.orders = {}
        self.error_marked = False

    def unresolved_critical_high(self):
        return []

    def verify_live_risk_decision(self, risk):
        return True, []

    def reserve_order_intent(self, intent, payload):
        row = self.orders.get(intent.idempotency_key)
        if row:
            return False, row
        row = {
            'signal_id': intent.signal_id,
            'risk_decision_id': intent.risk_decision_id,
            'client_order_id': intent.client_order_id,
            'exchange_order_id': None,
            'state': intent.state.value,
        }
        self.orders[intent.idempotency_key] = row
        return True, row

    def update_order_submitted(self, client_order_id, ack):
        for row in self.orders.values():
            if row['client_order_id'] == client_order_id:
                row['state'] = 'ORDER_SUBMITTED'
                row['exchange_order_id'] = ack['result']['orderId']

    def mark_order_error(self, client_order_id, reason):
        self.error_marked = True
        for row in self.orders.values():
            if row['client_order_id'] == client_order_id:
                row['state'] = 'ERROR_RECONCILIATION_REQUIRED'

    def create_incident(self, *args, **kwargs):
        pass


class CountingAdapter:
    calls = 0

    def __init__(self, *args, **kwargs):
        pass

    def place_order(self, payload):
        CountingAdapter.calls += 1
        return {'retCode': 0, 'result': {'orderId': 'ex-1', 'orderLinkId': payload['orderLinkId']}}


class FailingAdapter:
    def __init__(self, *args, **kwargs):
        pass

    def place_order(self, payload):
        raise RuntimeError('rest_timeout_after_submit_unknown')


def _install_live_test_state(monkeypatch, adapter_cls):
    import app.api.routes.execution as execution_route

    monkeypatch.setattr(execution_route, 'BybitAdapter', adapter_cls)
    old_settings = app.state.settings
    old_repo = getattr(app.state, 'repository', None)
    old_db_available = getattr(app.state, 'db_available', False)
    old_router = app.state.order_router
    app.state.settings = Settings(
        operator_api_key='operator-test',
        readonly_api_key='readonly-test',
        trading_enabled=True,
        bybit_live_confirm=True,
        enable_live_submit=True,
        bybit_api_key='k',
        bybit_api_secret='s',
        require_go_nogo_for_live=False,
        require_live_preflight=False,
    )
    app.state.repository = FakeRepo()
    app.state.db_available = True
    app.state.order_router = OrderRouter(InMemoryIdempotencyStore())
    return old_settings, old_repo, old_db_available, old_router


def _restore_state(saved):
    old_settings, old_repo, old_db_available, old_router = saved
    app.state.settings = old_settings
    app.state.repository = old_repo
    app.state.db_available = old_db_available
    app.state.order_router = old_router


def test_live_submit_repeated_idempotency_key_does_not_call_bybit_twice(monkeypatch):
    CountingAdapter.calls = 0
    saved = _install_live_test_state(monkeypatch, CountingAdapter)
    try:
        client = TestClient(app)
        headers = {'x-api-key': app.state.settings.operator_api_key, 'X-Idempotency-Key': 'idem-live-repeat'}
        first = client.post('/api/execution/live-submit', json=_payload(), headers=headers)
        second = client.post('/api/execution/live-submit', json=_payload(), headers=headers)
        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert CountingAdapter.calls == 1
        assert second.json()['data']['idempotent_replay'] is True
        assert second.json()['data']['stored_order_state'] == 'ORDER_SUBMITTED'
    finally:
        _restore_state(saved)


def test_live_submit_unknown_rest_result_marks_reconciliation_error(monkeypatch):
    saved = _install_live_test_state(monkeypatch, FailingAdapter)
    try:
        client = TestClient(app)
        headers = {'x-api-key': app.state.settings.operator_api_key, 'X-Idempotency-Key': 'idem-live-repeat'}
        response = client.post('/api/execution/live-submit', json=_payload(), headers=headers)
        assert response.status_code == 502
        assert response.json()['detail']['live_submit_uncertain_result'] == 'reconciliation_required'
        row = app.state.repository.orders['idem-live-repeat']
        assert row['state'] == 'ERROR_RECONCILIATION_REQUIRED'
        assert app.state.repository.error_marked is True
    finally:
        _restore_state(saved)

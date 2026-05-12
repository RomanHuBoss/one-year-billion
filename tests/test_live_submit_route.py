from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.time import utc_now


def test_live_submit_route_exists_but_is_locked_by_gates():
    now = utc_now()
    payload = {
        'idempotency_key': 'live-test-key',
        'signal': {
            'signal_id': '00000000-0000-0000-0000-000000000001',
            'strategy': 'micro_grid',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 100000,
            'stop_price': 99000,
            'invalidator': 'range_break',
            'expected_gross_edge_bps': 30,
            'trace_id': 't-live-route',
            'strategy_version': '1',
            'feature_hash': 'fh-live-route',
            'evidence': {'range_quality': 'ok'},
        },
        'risk_decision': {
            'risk_decision_id': '00000000-0000-0000-0000-000000000002',
            'signal_id': '00000000-0000-0000-0000-000000000001',
            'approved': True,
            'reasons': [],
            'sizing': {'qty': 0.001, 'notional': 100, 'risk_budget': 5, 'stop_distance_abs': 1000, 'max_loss_if_stop': 2, 'expected_net_edge_bps': 10},
            'limits_snapshot': {},
            'account_snapshot': {},
            'specs_version': 'runtime-v1',
            'feature_hash': 'fh-live-route',
            'config_hash': 'cfg',
            'trace_id': 't-live-route',
            'created_at': now.isoformat(),
            'expires_at': (now + timedelta(seconds=60)).isoformat(),
        },
    }
    client = TestClient(app)
    r = client.post('/api/execution/live-submit', json=payload, headers={'x-api-key': app.state.settings.operator_api_key, 'X-Idempotency-Key': 'live-test-key'})
    assert r.status_code == 423
    assert 'live_submit_blocked' in str(r.json())

from fastapi.testclient import TestClient
from app.core.settings import Settings
from app.main import app


def test_live_risk_approval_blocks_without_database(monkeypatch):
    old_settings = app.state.settings
    old_repo = getattr(app.state, 'repository', None)
    try:
        app.state.settings = Settings(
            trading_enabled=True,
            bybit_live_confirm=True,
            enable_live_submit=True,
            bybit_api_key='k',
            bybit_api_secret='s',
            require_go_nogo_for_live=False,
            require_live_preflight=False,
        )
        app.state.repository = None
        candidate = {
            'signal_id': '00000000-0000-0000-0000-000000000201',
            'strategy': 'micro_grid',
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'entry_price': 100000,
            'stop_price': 99000,
            'invalidator': 'range_break',
            'expected_gross_edge_bps': 30,
            'trace_id': 't-live-risk-db',
            'strategy_version': '1',
            'feature_hash': 'fh-live-risk-db',
            'evidence': {'range_quality': 'ok'},
        }
        response = TestClient(app).post('/api/risk/approve', json=candidate)
        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'blocked'
        assert 'database_required_for_live_risk_approval' in payload['reasons']
    finally:
        app.state.settings = old_settings
        app.state.repository = old_repo

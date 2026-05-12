from app.core.settings import Settings
from app.config.runtime import build_runtime_config
from app.live.preflight import run_live_preflight


class FakeAdapterOK:
    def get_server_time(self):
        return {'retCode': 0, 'time': 123}

    def runtime_instruments_info(self, symbol):
        return {'retCode': 0, 'result': {'list': [{
            'symbol': symbol,
            'category': 'linear',
            'status': 'Trading',
            'priceFilter': {'tickSize': '0.1'},
            'lotSizeFilter': {'qtyStep': '0.001', 'minOrderQty': '0.001', 'minNotionalValue': '5'},
            'leverageFilter': {'maxLeverage': '100'},
        }]}}

    def get_wallet_balance(self):
        return {'retCode': 0, 'result': {'list': [{'accountType': 'UNIFIED'}]}}

    def get_positions(self):
        return {'retCode': 0, 'result': {'list': []}}

    def get_api_key_info(self):
        return {'retCode': 0, 'result': {'permissions': {'ContractTrade': ['Order', 'Position']}}}


class FakeRepo:
    def unresolved_critical_high(self):
        return []

    def live_evidence_status(self, min_paper_days, config_hash):
        return True, [], {'paper_days': min_paper_days}


def test_live_preflight_blocks_without_explicit_live_submit():
    runtime = build_runtime_config()
    settings = Settings(
        trading_enabled=True,
        bybit_live_confirm=True,
        enable_live_submit=False,
        bybit_api_key='k',
        bybit_api_secret='s',
        require_go_nogo_for_live=False,
        require_live_preflight=False,
    )
    result = run_live_preflight(settings, runtime, db_available=True, repository=FakeRepo())
    assert result.status == 'blocked'
    assert 'cas_enable_live_submit_false' in result.reasons


def test_live_preflight_passes_with_all_gates_and_runtime_checks():
    runtime = build_runtime_config()
    settings = Settings(
        trading_enabled=True,
        bybit_live_confirm=True,
        enable_live_submit=True,
        bybit_api_key='k',
        bybit_api_secret='s',
        live_go_nogo_passed=True,
        live_approved_by='product-owner',
        require_go_nogo_for_live=True,
        require_live_preflight=True,
    )
    result = run_live_preflight(settings, runtime, db_available=True, repository=FakeRepo(), adapter=FakeAdapterOK())
    assert result.status == 'ok'
    assert result.checks['bybit_private_api_and_permissions_verified'] is True
    assert result.data['runtime_specs']['BTCUSDT']['status'] == 'Trading'


def test_settings_reads_environment_at_instance_time(monkeypatch):
    monkeypatch.setenv('CAS_ENABLE_LIVE_SUBMIT', 'true')
    monkeypatch.setenv('TRADING_ENABLED', 'true')
    monkeypatch.setenv('BYBIT_LIVE_CONFIRM', 'true')
    monkeypatch.setenv('BYBIT_API_KEY', 'k')
    monkeypatch.setenv('BYBIT_API_SECRET', 's')
    s = Settings()
    assert s.enable_live_submit is True
    assert s.can_live_trade is True


class FakeRepoNoEvidence:
    def unresolved_critical_high(self):
        return []

    def live_evidence_status(self, min_paper_days, config_hash):
        return False, ['phase0_paper_evidence_missing_or_too_short'], {'paper_days': 0}


def test_live_preflight_blocks_when_go_no_go_env_is_set_but_db_evidence_missing():
    runtime = build_runtime_config()
    settings = Settings(
        trading_enabled=True,
        bybit_live_confirm=True,
        enable_live_submit=True,
        bybit_api_key='k',
        bybit_api_secret='s',
        live_go_nogo_passed=True,
        live_approved_by='product-owner',
        require_go_nogo_for_live=True,
        require_live_preflight=False,
    )
    result = run_live_preflight(settings, runtime, db_available=True, repository=FakeRepoNoEvidence())
    assert result.status == 'blocked'
    assert 'phase0_paper_evidence_missing_or_too_short' in result.reasons
    assert result.checks['go_no_go_approved'] is False


class FakeAdapterNoTradePermission(FakeAdapterOK):
    def get_api_key_info(self):
        return {'retCode': 0, 'result': {'permissions': {'ReadOnly': ['Wallet']}}}


def test_live_preflight_blocks_when_trade_permission_not_verified():
    runtime = build_runtime_config()
    settings = Settings(
        trading_enabled=True,
        bybit_live_confirm=True,
        enable_live_submit=True,
        bybit_api_key='k',
        bybit_api_secret='s',
        live_go_nogo_passed=True,
        live_approved_by='product-owner',
        require_go_nogo_for_live=True,
        require_live_preflight=True,
    )
    result = run_live_preflight(settings, runtime, db_available=True, repository=FakeRepo(), adapter=FakeAdapterNoTradePermission())
    assert result.status == 'blocked'
    assert 'bybit_api_key_trade_permission_not_verified' in result.reasons
    assert result.checks['bybit_private_api_and_permissions_verified'] is False


class FakeAdapterMissingQtyStep(FakeAdapterOK):
    def runtime_instruments_info(self, symbol):
        payload = super().runtime_instruments_info(symbol)
        payload['result']['list'][0]['lotSizeFilter'].pop('qtyStep')
        return payload


def test_live_preflight_blocks_when_runtime_specs_are_incomplete():
    runtime = build_runtime_config()
    settings = Settings(
        trading_enabled=True,
        bybit_live_confirm=True,
        enable_live_submit=True,
        bybit_api_key='k',
        bybit_api_secret='s',
        live_go_nogo_passed=True,
        live_approved_by='product-owner',
        require_go_nogo_for_live=True,
        require_live_preflight=True,
    )
    result = run_live_preflight(settings, runtime, db_available=True, repository=FakeRepo(), adapter=FakeAdapterMissingQtyStep())
    assert result.status == 'blocked'
    assert result.checks['runtime_instrument_specs_verified'] is False
    assert any('runtime_specs_missing_or_nonpositive:qty_step' in reason for reason in result.reasons)


def test_testnet_preflight_does_not_require_live_submit_or_go_no_go():
    runtime = build_runtime_config()
    settings = Settings(
        bybit_testnet=True,
        trading_enabled=False,
        bybit_live_confirm=False,
        enable_live_submit=False,
        bybit_api_key='',
        bybit_api_secret='',
        require_go_nogo_for_live=True,
        require_live_preflight=True,
    )
    result = run_live_preflight(settings, runtime, db_available=True, repository=FakeRepo(), mode='testnet')
    assert result.status == 'blocked'
    assert 'testnet_bybit_credentials_missing' in result.reasons
    assert 'cas_enable_live_submit_false' not in result.reasons
    assert 'go_no_go_pass_and_approver_required' not in result.reasons
    assert result.data['go_no_go_required_for_testnet'] is False

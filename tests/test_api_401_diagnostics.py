import httpx
import pytest

from app.execution.bybit_adapter import BybitAPIError, BybitAdapter, BybitConfig


def test_bybit_http_401_invalid_api_key_is_normalized_without_secret_leak():
    adapter = BybitAdapter(BybitConfig('public-key', 'fake-secret'))
    response = httpx.Response(401, json={'detail': 'invalid_api_key'}, request=httpx.Request('GET', 'https://api-testnet.bybit.com/v5/user/query-api'))

    with pytest.raises(BybitAPIError) as excinfo:
        adapter._raise_http_status_error(response, path='/v5/user/query-api')

    exc = excinfo.value
    assert exc.code == 'invalid_api_key'
    assert exc.http_status == 401
    assert exc.reason_code() == 'invalid_api_key_http_401'
    assert 'fake-secret' not in str(exc)
    assert 'public-key' not in str(exc)


def test_frontend_explains_backend_invalid_api_key_and_sends_read_key():
    api_client = open('frontend/js/api_client.js', encoding='utf-8').read()
    app_js = open('frontend/js/app.js', encoding='utf-8').read()
    index = open('frontend/index.html', encoding='utf-8').read()

    assert 'API-доступ' in index
    assert 'Это не ключ Bybit' in api_client
    assert 'readAuthOptions()' in app_js
    assert "api('/api/operator/dashboard', readAuthOptions())" in app_js
    assert "api('/api/operator/commands', readAuthOptions())" in app_js
    assert "'x-api-key': key" in app_js

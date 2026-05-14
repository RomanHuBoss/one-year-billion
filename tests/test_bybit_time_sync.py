import pytest

import app.execution.bybit_adapter as bybit_module
from app.execution.bybit_adapter import BybitAPIError, BybitAdapter, BybitConfig
from app.live.preflight import _operator_hint_for_bybit_private_errors


def test_bybit_adapter_uses_server_time_offset_for_private_headers(monkeypatch):
    """retCode=10002 часто возникает, когда локальные часы впереди Bybit > 1000 мс."""

    adapter = BybitAdapter(BybitConfig(
        api_key='public-key',
        api_secret='secret-key',
        recv_window_ms=8000,
        time_safety_margin_ms=250,
    ))

    # Локальная машина ушла вперед примерно на 1.35 сек относительно Bybit.
    times = iter([1778736696.000, 1778736696.100, 1778736696.200, 1778736696.200])
    monkeypatch.setattr(bybit_module.time, 'time', lambda: next(times))
    monkeypatch.setattr(adapter, '_public_get', lambda path: {'retCode': 0, 'time': 1778736694700})

    sync_payload = adapter.sync_time()
    headers = adapter._headers('category=linear&settleCoin=USDT')

    assert sync_payload['time'] == 1778736694700
    assert headers['X-BAPI-RECV-WINDOW'] == '8000'
    # Timestamp теперь берется от Bybit server time minus safety margin, а не от
    # локальных часов, которые в этом тесте опережают сервер.
    assert int(headers['X-BAPI-TIMESTAMP']) == 1778736694600
    assert adapter.time_sync_status()['server_time_offset_ms'] == -1350
    assert 'secret-key' not in str(adapter.time_sync_status())


def test_bybit_timestamp_window_error_is_classified_with_safe_details():
    adapter = BybitAdapter(BybitConfig('public-key', 'secret-key'))
    payload = {
        'retCode': 10002,
        'retMsg': 'invalid request, please check your server timestamp or recv_window param',
    }

    with pytest.raises(BybitAPIError) as excinfo:
        adapter._raise_if_bybit_rejected(payload, path='/v5/user/query-api')

    exc = excinfo.value
    assert exc.code == 'bybit_timestamp_window_error'
    assert exc.reason_code() == 'bybit_timestamp_window_error_10002'
    safe = exc.safe_dict()
    assert safe['ret_code'] == 10002
    assert safe['details']['recv_window_ms'] == 8000
    assert 'secret-key' not in str(safe)
    assert 'public-key' not in str(safe)


def test_operator_hint_for_retcode_10002_points_to_time_sync_not_bad_key():
    hints = _operator_hint_for_bybit_private_errors([
        {'code': 'bybit_timestamp_window_error', 'ret_code': 10002, 'ret_msg': 'timestamp recv_window'}
    ])

    assert hints
    assert 'retCode=10002' in hints[0]
    assert 'не плохой ключ' in hints[0]
    assert 'синхронизацию часов Windows' in hints[0]

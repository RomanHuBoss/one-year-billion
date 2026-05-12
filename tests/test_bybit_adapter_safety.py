import pytest
from app.execution.bybit_adapter import BybitAdapter, BybitConfig


def test_bybit_nonzero_retcode_is_not_success():
    adapter = BybitAdapter(BybitConfig(api_key='k', api_secret='s'))
    with pytest.raises(RuntimeError, match='bybit_request_rejected'):
        adapter._raise_if_bybit_rejected({'retCode': 110001, 'retMsg': 'Order does not exist'})


def test_reduce_only_market_exit_sets_close_on_trigger():
    adapter = BybitAdapter(BybitConfig(api_key='k', api_secret='s'))
    ack = adapter.reduce_only_market_exit('BTCUSDT', 'Sell', '0.001', 'cas26-exit-test')
    assert ack['retCode'] == 0
    # Проверяем payload через публичный place_order guard невозможно напрямую из ack,
    # поэтому ниже фиксируем контракт helper-а monkeypatch-ом.
    captured = {}
    class CaptureAdapter(BybitAdapter):
        def place_order(self, payload):
            captured.update(payload)
            return {'retCode': 0}
    CaptureAdapter(BybitConfig(api_key='k', api_secret='s')).reduce_only_market_exit('BTCUSDT', 'Sell', '0.001', 'cas26-exit-test')
    assert captured['reduceOnly'] is True
    assert captured['closeOnTrigger'] is True
    assert captured['category'] == 'linear'

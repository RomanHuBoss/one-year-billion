import pytest
from app.execution.bybit_adapter import BybitAdapter, BybitConfig


def test_bybit_nonzero_retcode_is_not_success():
    adapter = BybitAdapter(BybitConfig(api_key='k', api_secret='s'))
    with pytest.raises(RuntimeError, match='bybit_request_rejected'):
        adapter._raise_if_bybit_rejected({'retCode': 110001, 'retMsg': 'Order does not exist'})

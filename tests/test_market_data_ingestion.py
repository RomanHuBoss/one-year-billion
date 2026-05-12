import pytest
from app.market_data.bybit_ingestion import normalize_instrument, normalize_orderbook


def test_normalize_instrument_rejects_non_linear():
    with pytest.raises(ValueError, match='instrument_category_not_linear'):
        normalize_instrument({'symbol': 'BTCUSDT', 'category': 'spot'})


def test_normalize_orderbook_builds_spread_and_depth():
    snap = normalize_orderbook('BTCUSDT', {'result': {'b': [['100', '2']], 'a': [['101', '3']]}})
    assert snap.symbol == 'BTCUSDT'
    assert snap.spread_bps > 0
    assert snap.depth_usdt == 503

from app.market_data.bybit_ingestion import BybitMarketDataIngestion


class _AdapterNoFunding:
    def get_orderbook(self, symbol):
        return {'result': {'b': [['100', '2']], 'a': [['101', '3']]}}

    def get_funding_history(self, symbol):
        return {'result': {'list': []}}


def test_live_market_snapshot_requires_funding_component():
    ingestion = BybitMarketDataIngestion(_AdapterNoFunding())
    with pytest.raises(RuntimeError, match='funding_runtime_data_missing'):
        ingestion.fetch_market_snapshot('BTCUSDT')

class _AdapterWithPosition:
    def get_wallet_balance(self):
        return {'result': {'list': [{'accountType': 'UNIFIED', 'totalEquity': '500', 'totalAvailableBalance': '450'}]}}

    def get_positions(self):
        return {'result': {'list': [{'symbol': 'BTCUSDT', 'size': '0.01'}]}}


def test_live_account_snapshot_flags_any_open_position_for_entry_gate():
    account = BybitMarketDataIngestion(_AdapterWithPosition()).fetch_account_snapshot(phase=0)
    assert account.position_mismatch is True

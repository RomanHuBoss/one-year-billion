from __future__ import annotations
from datetime import timedelta
from typing import Any
from app.core.hashes import hash_payload
from app.core.time import utc_now
from app.execution.bybit_adapter import BybitAdapter
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot


def _float_nested(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_instrument(item: dict[str, Any], ttl_seconds: int = 3600) -> InstrumentSpec:
    """Нормализует Bybit instruments-info в внутренний contract.

    Нельзя hardcode minQty/minNotional/tickSize/qtyStep: эти параметры
    считаются runtime specs и должны обновляться перед risk approval.
    """

    now = utc_now()
    lot = item.get('lotSizeFilter') or {}
    price = item.get('priceFilter') or {}
    leverage = item.get('leverageFilter') or {}
    category = item.get('category') or 'linear'
    if category != 'linear':
        raise ValueError('instrument_category_not_linear')
    return InstrumentSpec(
        symbol=str(item['symbol']).upper(),
        category='linear',
        status=item.get('status', 'UNKNOWN'),
        tick_size=_float_nested(price.get('tickSize'), 0.0),
        qty_step=_float_nested(lot.get('qtyStep'), 0.0),
        min_qty=_float_nested(lot.get('minOrderQty'), 0.0),
        min_notional=_float_nested(lot.get('minNotionalValue'), 0.0),
        max_leverage=_float_nested(leverage.get('maxLeverage'), 1.0),
        specs_version=hash_payload(item)[:16],
        fetched_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )


def normalize_orderbook(symbol: str, payload: dict[str, Any], funding_bps: float = 0.0, ttl_seconds: int = 10) -> MarketSnapshot:
    result = payload.get('result') or {}
    bids = result.get('b') or result.get('bids') or []
    asks = result.get('a') or result.get('asks') or []
    if not bids or not asks:
        raise ValueError('empty_orderbook')
    bid1 = _float_nested(bids[0][0])
    ask1 = _float_nested(asks[0][0])
    if bid1 <= 0 or ask1 <= 0 or ask1 < bid1:
        raise ValueError('invalid_top_of_book')
    mid = (bid1 + ask1) / 2
    spread_bps = (ask1 - bid1) / mid * 10000
    # Упрощенная глубина top-N: quote notional sum around snapshot.
    depth = sum(_float_nested(px) * _float_nested(qty) for px, qty, *_ in bids[:10]) + sum(_float_nested(px) * _float_nested(qty) for px, qty, *_ in asks[:10])
    now = utc_now()
    return MarketSnapshot(
        symbol=symbol.upper(),
        bid1=bid1,
        ask1=ask1,
        spread_bps=spread_bps,
        depth_usdt=depth,
        funding_bps=funding_bps,
        fetched_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )


class BybitMarketDataIngestion:
    def __init__(self, adapter: BybitAdapter):
        self.adapter = adapter

    def fetch_runtime_specs(self, symbol: str) -> InstrumentSpec:
        payload = self.adapter.runtime_instruments_info(symbol)
        items = (payload.get('result') or {}).get('list') or []
        if not items:
            raise RuntimeError(f'{symbol}:instrument_not_found')
        return normalize_instrument(items[0])

    def fetch_market_snapshot(self, symbol: str) -> MarketSnapshot:
        orderbook = self.adapter.get_orderbook(symbol)
        funding = self.adapter.get_funding_history(symbol)
        rows = (funding.get('result') or {}).get('list') or []
        if not rows:
            # Funding входит в cost model. Для live risk approval отсутствие
            # funding не маскируется нулем, а fail-closed блокирует сделку.
            raise RuntimeError(f'{symbol}:funding_runtime_data_missing')
        funding_bps = _float_nested(rows[0].get('fundingRate')) * 10000
        return normalize_orderbook(symbol, orderbook, funding_bps=funding_bps)

    def fetch_account_snapshot(self, phase: int = 0) -> AccountSnapshot:
        wallet = self.adapter.get_wallet_balance()
        rows = (wallet.get('result') or {}).get('list') or []
        if not rows:
            raise RuntimeError('wallet_balance_runtime_data_missing')
        row = rows[0]
        # Bybit Unified обычно отдает totalEquity/totalAvailableBalance.
        # Для некоторых аккаунтов поля могут отличаться, поэтому fallback идет
        # через coin[USDT], но если equity не положительный, live risk approval
        # будет заблокирован.
        coins = row.get('coin') or []
        usdt = next((c for c in coins if str(c.get('coin')).upper() == 'USDT'), {})
        equity = _float_nested(row.get('totalEquity'), 0.0) or _float_nested(usdt.get('equity'), 0.0) or _float_nested(usdt.get('walletBalance'), 0.0)
        available = _float_nested(row.get('totalAvailableBalance'), 0.0) or _float_nested(usdt.get('availableToWithdraw'), 0.0) or equity
        if equity <= 0:
            raise RuntimeError('account_equity_not_positive')
        now = utc_now()
        positions = self.adapter.get_positions()
        pos_rows = (positions.get('result') or {}).get('list') or []
        nonflat_positions = [p for p in pos_rows if _float_nested(p.get('size'), 0.0) > 0]
        portfolio_abs_notional = sum(
            _float_nested(p.get('size'), 0.0) * (
                _float_nested(p.get('markPrice'), 0.0)
                or _float_nested(p.get('avgPrice'), 0.0)
                or _float_nested(p.get('entryPrice'), 0.0)
            )
            for p in nonflat_positions
        )
        return AccountSnapshot(
            equity_usdt=equity,
            available_balance_usdt=max(available, 0.0),
            phase=phase,
            account_mode=str(row.get('accountType') or 'UNIFIED'),
            # Для entry risk approval любые уже открытые exchange positions
            # переводят систему в fail-closed до reconciliation. Это защищает
            # Phase 0 max-one-position scope от скрытого exposure.
            position_mismatch=bool(nonflat_positions),
            portfolio_abs_notional_usdt=portfolio_abs_notional,
            beta_adjusted_exposure_usdt=portfolio_abs_notional,
            fetched_at=now,
            expires_at=now + timedelta(seconds=30),
        )

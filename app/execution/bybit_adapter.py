from __future__ import annotations
import hmac, hashlib, time, json
from dataclasses import dataclass
from typing import Any
import httpx
from app.core.hashes import hash_payload
from app.execution.rate_limiter import TokenBucketRateLimiter


@dataclass(frozen=True)
class BybitConfig:
    api_key: str
    api_secret: str
    testnet: bool = True
    trading_enabled: bool = False
    live_confirm: bool = False

    @property
    def base_url(self) -> str:
        return 'https://api-testnet.bybit.com' if self.testnet else 'https://api.bybit.com'


class BybitAdapter:
    """Граница Bybit V5. Live-submit закрыт флагами; category всегда только linear."""

    def __init__(self, cfg: BybitConfig, limiter: TokenBucketRateLimiter | None = None):
        self.cfg = cfg
        self.limiter = limiter or TokenBucketRateLimiter()
        self.degraded_reason: str | None = None

    def _guard_rate_limit(self) -> None:
        if not self.limiter.allow():
            self.degraded_reason = 'local_rate_limiter_open'
            raise RuntimeError('exchange_degraded:local_rate_limiter_open')

    def _sign(self, timestamp: str, recv_window: str, payload: str) -> str:
        raw = f'{timestamp}{self.cfg.api_key}{recv_window}{payload}'
        return hmac.new(self.cfg.api_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()

    def _headers(self, payload: str) -> dict[str, str]:
        ts = str(int(time.time() * 1000))
        recv = '5000'
        return {
            'X-BAPI-API-KEY': self.cfg.api_key,
            'X-BAPI-TIMESTAMP': ts,
            'X-BAPI-RECV-WINDOW': recv,
            'X-BAPI-SIGN': self._sign(ts, recv, payload),
            'Content-Type': 'application/json',
        }

    def _raise_if_bybit_degraded(self, payload: dict[str, Any]) -> None:
        ret_code = payload.get('retCode')
        if ret_code in {429, 10006}:
            self.degraded_reason = f'bybit_rate_limit:{ret_code}'
            raise RuntimeError(self.degraded_reason)

    def _raise_if_bybit_rejected(self, payload: dict[str, Any]) -> None:
        """Любой retCode != 0 не должен выглядеть как успешный submit."""

        ret_code = payload.get('retCode')
        if ret_code not in (0, '0', None):
            message = payload.get('retMsg', 'unknown')
            raise RuntimeError(f'bybit_request_rejected:{ret_code}:{message}')

    def _public_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._guard_rate_limit()
        with httpx.Client(timeout=10) as client:
            r = client.get(f'{self.cfg.base_url}{path}', params=params or {})
            if r.status_code == 429:
                self.degraded_reason = 'http_429'
                raise RuntimeError('exchange_degraded:http_429')
            r.raise_for_status()
            data = r.json()
            self._raise_if_bybit_degraded(data)
            self._raise_if_bybit_rejected(data)
            return data

    def _private_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.cfg.api_key or not self.cfg.api_secret:
            raise RuntimeError('bybit_credentials_missing')
        self._guard_rate_limit()
        params = params or {}
        query = '&'.join(f'{k}={v}' for k, v in sorted(params.items()) if v is not None)
        headers = self._headers(query)
        with httpx.Client(timeout=10) as client:
            r = client.get(f'{self.cfg.base_url}{path}', params=params, headers=headers)
            if r.status_code == 429:
                self.degraded_reason = 'http_429'
                raise RuntimeError('exchange_degraded:http_429')
            r.raise_for_status()
            data = r.json()
            self._raise_if_bybit_degraded(data)
            self._raise_if_bybit_rejected(data)
            return data

    def _private_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.cfg.api_key or not self.cfg.api_secret:
            raise RuntimeError('bybit_credentials_missing')
        self._guard_rate_limit()
        body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        with httpx.Client(timeout=10) as client:
            r = client.post(f'{self.cfg.base_url}{path}', content=body, headers=self._headers(body))
            if r.status_code == 429:
                self.degraded_reason = 'http_429'
                raise RuntimeError('exchange_degraded:http_429')
            r.raise_for_status()
            data = r.json()
            self._raise_if_bybit_degraded(data)
            self._raise_if_bybit_rejected(data)
            return data

    def get_server_time(self) -> dict[str, Any]:
        return self._public_get('/v5/market/time')

    def runtime_instruments_info(self, symbol: str) -> dict[str, Any]:
        params = {'category': 'linear', 'symbol': symbol.upper()}
        data = self._public_get('/v5/market/instruments-info', params=params)
        for item in data.get('result', {}).get('list', []):
            if item.get('category') and item.get('category') != 'linear':
                raise RuntimeError('runtime_instrument_category_not_linear')
        return data

    def fetch_linear_instruments_page(self, cursor: str | None = None, limit: int = 500) -> dict[str, Any]:
        params: dict[str, Any] = {'category': 'linear', 'limit': limit}
        if cursor:
            params['cursor'] = cursor
        return self._public_get('/v5/market/instruments-info', params=params)

    def fetch_all_linear_instruments(self, max_pages: int = 20) -> list[dict[str, Any]]:
        instruments: list[dict[str, Any]] = []
        cursor: str | None = None
        for _ in range(max_pages):
            page = self.fetch_linear_instruments_page(cursor=cursor)
            result = page.get('result') or {}
            instruments.extend(result.get('list') or [])
            cursor = result.get('nextPageCursor') or None
            if not cursor:
                break
        return instruments

    def get_orderbook(self, symbol: str, limit: int = 50) -> dict[str, Any]:
        return self._public_get('/v5/market/orderbook', {'category': 'linear', 'symbol': symbol.upper(), 'limit': limit})

    def get_funding_history(self, symbol: str, limit: int = 1) -> dict[str, Any]:
        return self._public_get('/v5/market/funding/history', {'category': 'linear', 'symbol': symbol.upper(), 'limit': limit})

    def get_open_interest(self, symbol: str, interval_time: str = '5min', limit: int = 1) -> dict[str, Any]:
        return self._public_get('/v5/market/open-interest', {'category': 'linear', 'symbol': symbol.upper(), 'intervalTime': interval_time, 'limit': limit})

    def get_wallet_balance(self, account_type: str = 'UNIFIED') -> dict[str, Any]:
        return self._private_get('/v5/account/wallet-balance', {'accountType': account_type, 'coin': 'USDT'})

    def get_positions(self, settle_coin: str = 'USDT') -> dict[str, Any]:
        return self._private_get('/v5/position/list', {'category': 'linear', 'settleCoin': settle_coin})

    def get_api_key_info(self) -> dict[str, Any]:
        # Runtime permissions check. Если Bybit меняет формат ответа, preflight
        # fail-closed вернет BLOCKED до адаптации parser-а.
        return self._private_get('/v5/user/query-api')

    def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get('category') != 'linear':
            raise ValueError('category_must_be_linear')
        if not payload.get('orderLinkId') or len(str(payload.get('orderLinkId'))) > 36:
            raise ValueError('invalid_orderLinkId')
        if not (self.cfg.trading_enabled and self.cfg.live_confirm):
            return {'retCode': 0, 'mode': 'paper_ack', 'result': {'orderId': f'paper-{hash_payload(payload)[:16]}', 'orderLinkId': payload.get('orderLinkId')}}
        return self._private_post('/v5/order/create', payload)

    def cancel_all_entries(self, symbol: str) -> dict[str, Any]:
        # Safety action: отмена заявок не увеличивает риск.
        payload = {'category': 'linear', 'symbol': symbol.upper(), 'settleCoin': 'USDT'}
        return self._private_post('/v5/order/cancel-all', payload)

    def reduce_only_market_exit(self, symbol: str, side: str, qty: str, order_link_id: str) -> dict[str, Any]:
        # Emergency flatten: reduceOnly + market. Реальное исполнение затем обязан
        # подтвердить reconciliation, market ack не считается fill.
        payload = {
            'category': 'linear',
            'symbol': symbol.upper(),
            'side': side,
            'orderType': 'Market',
            'qty': qty,
            'reduceOnly': True,
            'orderLinkId': order_link_id,
        }
        return self.place_order(payload)

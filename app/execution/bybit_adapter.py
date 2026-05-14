from __future__ import annotations
import hmac, hashlib, time, json
from dataclasses import dataclass
from typing import Any
import httpx
from app.core.hashes import hash_payload
from app.execution.rate_limiter import TokenBucketRateLimiter


class BybitAPIError(RuntimeError):
    """Нормализованная ошибка Bybit для preflight и операторского интерфейса.

    В message нет ключей/секретов. Ошибка сохраняет retCode/retMsg/path, чтобы
    оператор видел причину блокировки вместо общего RuntimeError.
    """

    def __init__(
        self,
        code: str,
        message: str = '',
        *,
        ret_code: Any = None,
        ret_msg: str | None = None,
        path: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.code = code
        self.ret_code = ret_code
        self.ret_msg = ret_msg or message
        self.path = path
        self.http_status = http_status
        self.details = details or {}
        parts = [code]
        if ret_code is not None:
            parts.append(str(ret_code))
        if self.ret_msg:
            parts.append(str(self.ret_msg))
        if path:
            parts.append(f'path={path}')
        if http_status is not None:
            parts.append(f'http={http_status}')
        super().__init__(':'.join(parts))

    def reason_code(self) -> str:
        if self.ret_code is not None:
            return f'{self.code}_{self.ret_code}'
        if self.http_status is not None:
            return f'{self.code}_http_{self.http_status}'
        return self.code

    def safe_dict(self) -> dict[str, Any]:
        data = {
            'code': self.code,
            'ret_code': self.ret_code,
            'ret_msg': self.ret_msg,
            'path': self.path,
            'http_status': self.http_status,
        }
        if self.details:
            data['details'] = self.details
        return data


@dataclass(frozen=True)
class BybitConfig:
    api_key: str
    api_secret: str
    testnet: bool = True
    trading_enabled: bool = False
    live_confirm: bool = False
    recv_window_ms: int = 8000
    time_sync_ttl_sec: int = 60
    time_safety_margin_ms: int = 250
    auto_time_sync: bool = True

    @property
    def base_url(self) -> str:
        return 'https://api-testnet.bybit.com' if self.testnet else 'https://api.bybit.com'


class BybitAdapter:
    """Граница Bybit V5. Live-submit закрыт флагами; category всегда только linear."""

    def __init__(self, cfg: BybitConfig, limiter: TokenBucketRateLimiter | None = None):
        self.cfg = cfg
        self.limiter = limiter or TokenBucketRateLimiter()
        self.degraded_reason: str | None = None
        self._server_time_offset_ms: int | None = None
        self._server_time_synced_at_ms: int | None = None
        self._last_server_time_ms: int | None = None
        self._last_time_sync_error: str | None = None

    def _guard_rate_limit(self) -> None:
        if not self.limiter.allow():
            self.degraded_reason = 'local_rate_limiter_open'
            raise BybitAPIError('exchange_degraded', 'local_rate_limiter_open')

    @staticmethod
    def _local_time_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def _extract_server_time_ms(payload: dict[str, Any]) -> int | None:
        """Достает Bybit server time из V5 `/v5/market/time` без предположений о форме ответа.

        Bybit обычно возвращает `time` на верхнем уровне и `result.timeNano`.
        В тестах/старых SDK может быть только одно из этих полей. Если timestamp
        не распознан, private request не должен молча считаться синхронизированным.
        """

        candidates = [
            payload.get('time'),
            (payload.get('result') or {}).get('timeNano'),
            (payload.get('result') or {}).get('timeSecond'),
            payload.get('time_now'),
        ]
        for raw in candidates:
            if raw is None:
                continue
            try:
                text = str(raw)
                # timeNano приходит в наносекундах; timeSecond — в секундах.
                if len(text.split('.')[0]) >= 18:
                    return int(int(float(text)) / 1_000_000)
                if len(text.split('.')[0]) <= 10:
                    return int(float(text) * 1000)
                return int(float(text))
            except (TypeError, ValueError, OverflowError):
                continue
        return None

    def sync_time(self) -> dict[str, Any]:
        """Синхронизирует подпись private API с Bybit server time.

        Bybit требует, чтобы timestamp лежал в окне
        `server_time - recv_window <= timestamp < server_time + 1000`.
        Поэтому `recv_window` не спасает, если локальные часы убежали вперед
        больше чем на 1 секунду. Мы используем смещение относительно серверного
        времени и небольшой safety margin, чтобы не получать retCode=10002.
        """

        local_before = self._local_time_ms()
        payload = self._public_get('/v5/market/time')
        local_after = self._local_time_ms()
        server_ms = self._extract_server_time_ms(payload)
        if server_ms is None:
            self._last_time_sync_error = 'server_time_not_parseable'
            raise BybitAPIError('bybit_time_sync_failed', 'server_time_not_parseable', path='/v5/market/time')
        midpoint = int((local_before + local_after) / 2)
        self._server_time_offset_ms = server_ms - midpoint
        self._server_time_synced_at_ms = local_after
        self._last_server_time_ms = server_ms
        self._last_time_sync_error = None
        return payload

    def _ensure_time_sync(self) -> None:
        if not self.cfg.auto_time_sync:
            return
        now_ms = self._local_time_ms()
        ttl_ms = max(1, int(self.cfg.time_sync_ttl_sec)) * 1000
        if self._server_time_offset_ms is None or self._server_time_synced_at_ms is None or now_ms - self._server_time_synced_at_ms > ttl_ms:
            self.sync_time()

    def _timestamp_for_private_ms(self) -> int:
        self._ensure_time_sync()
        base = self._local_time_ms()
        if self._server_time_offset_ms is not None:
            base += self._server_time_offset_ms
        # Safety margin нужен именно против верхней границы server_time + 1000.
        return base - max(0, int(self.cfg.time_safety_margin_ms))

    def time_sync_status(self) -> dict[str, Any]:
        return {
            'enabled': bool(self.cfg.auto_time_sync),
            'server_time_offset_ms': self._server_time_offset_ms,
            'synced_at_local_ms': self._server_time_synced_at_ms,
            'last_server_time_ms': self._last_server_time_ms,
            'recv_window_ms': int(self.cfg.recv_window_ms),
            'time_safety_margin_ms': int(self.cfg.time_safety_margin_ms),
            'last_error': self._last_time_sync_error,
        }

    def _sign(self, timestamp: str, recv_window: str, payload: str) -> str:
        raw = f'{timestamp}{self.cfg.api_key}{recv_window}{payload}'
        return hmac.new(self.cfg.api_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()

    def _headers(self, payload: str) -> dict[str, str]:
        ts = str(self._timestamp_for_private_ms())
        recv = str(int(self.cfg.recv_window_ms))
        return {
            'X-BAPI-API-KEY': self.cfg.api_key,
            'X-BAPI-TIMESTAMP': ts,
            'X-BAPI-RECV-WINDOW': recv,
            'X-BAPI-SIGN': self._sign(ts, recv, payload),
            'Content-Type': 'application/json',
        }

    def _raise_http_status_error(self, response: httpx.Response, path: str | None = None) -> None:
        """Нормализует HTTP 401/403/5xx без утечки заголовков и секретов.

        У Bybit и нашего operator API 401 часто приходит как JSON `invalid_api_key`.
        Оператор должен видеть явную причину блокировки, а не общий
        `HTTPStatusError`, но тело ответа нельзя прокидывать целиком: там могут
        быть диагностические детали, не предназначенные для UI.
        """

        if response.status_code == 429:
            self.degraded_reason = 'http_429'
            raise BybitAPIError('exchange_degraded', 'http_429', path=path, http_status=response.status_code)
        if response.is_success:
            return

        ret_code = None
        ret_msg = response.reason_phrase or 'http_status_error'
        try:
            payload = response.json()
            if isinstance(payload, dict):
                ret_code = payload.get('retCode') or payload.get('ret_code') or payload.get('code')
                detail = payload.get('retMsg') or payload.get('ret_msg') or payload.get('message') or payload.get('detail')
                if detail:
                    ret_msg = str(detail)
        except ValueError:
            pass

        normalized_msg = ret_msg.lower().replace(' ', '_')
        if response.status_code in {401, 403}:
            code = 'invalid_api_key' if 'invalid_api_key' in normalized_msg or 'invalid_api' in normalized_msg else 'bybit_private_auth_failed'
        elif response.status_code >= 500:
            code = 'exchange_degraded'
            self.degraded_reason = f'http_{response.status_code}'
        else:
            code = 'http_status_error'
        raise BybitAPIError(code, ret_msg, ret_code=ret_code, ret_msg=ret_msg, path=path, http_status=response.status_code)

    def _raise_if_bybit_degraded(self, payload: dict[str, Any], path: str | None = None) -> None:
        ret_code = payload.get('retCode')
        if ret_code in {429, 10006}:
            self.degraded_reason = f'bybit_rate_limit:{ret_code}'
            raise BybitAPIError('exchange_degraded', payload.get('retMsg', 'rate_limit'), ret_code=ret_code, ret_msg=payload.get('retMsg'), path=path)

    def _raise_if_bybit_rejected(self, payload: dict[str, Any], path: str | None = None) -> None:
        """Любой retCode != 0 не должен выглядеть как успешный submit."""

        ret_code = payload.get('retCode')
        if ret_code not in (0, '0', None):
            message = payload.get('retMsg', 'unknown')
            code = 'bybit_request_rejected'
            details: dict[str, Any] = {}
            if str(ret_code) == '10002' or 'recv_window' in str(message).lower() or 'timestamp' in str(message).lower():
                code = 'bybit_timestamp_window_error'
                details = self.time_sync_status()
                self._last_time_sync_error = str(message)
            raise BybitAPIError(code, message, ret_code=ret_code, ret_msg=message, path=path, details=details)

    def _public_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._guard_rate_limit()
        with httpx.Client(timeout=10) as client:
            r = client.get(f'{self.cfg.base_url}{path}', params=params or {})
            self._raise_http_status_error(r, path=path)
            data = r.json()
            self._raise_if_bybit_degraded(data, path=path)
            self._raise_if_bybit_rejected(data, path=path)
            return data

    def _private_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.cfg.api_key or not self.cfg.api_secret:
            raise BybitAPIError('bybit_credentials_missing', path=path)
        self._guard_rate_limit()
        params = params or {}
        query = '&'.join(f'{k}={v}' for k, v in sorted(params.items()) if v is not None)
        headers = self._headers(query)
        with httpx.Client(timeout=10) as client:
            r = client.get(f'{self.cfg.base_url}{path}', params=params, headers=headers)
            self._raise_http_status_error(r, path=path)
            data = r.json()
            self._raise_if_bybit_degraded(data, path=path)
            self._raise_if_bybit_rejected(data, path=path)
            return data

    def _private_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.cfg.api_key or not self.cfg.api_secret:
            raise BybitAPIError('bybit_credentials_missing', path=path)
        self._guard_rate_limit()
        body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        with httpx.Client(timeout=10) as client:
            r = client.post(f'{self.cfg.base_url}{path}', content=body, headers=self._headers(body))
            self._raise_http_status_error(r, path=path)
            data = r.json()
            self._raise_if_bybit_degraded(data, path=path)
            self._raise_if_bybit_rejected(data, path=path)
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
        symbol = str(payload.get('symbol') or '').upper()
        if not symbol or not symbol.endswith('USDT'):
            raise ValueError('symbol_must_be_linear_usdt_contract')
        if payload.get('orderType') not in {'Limit', 'Market'}:
            raise ValueError('order_type_not_allowed')
        if payload.get('side') not in {'Buy', 'Sell'}:
            raise ValueError('side_not_allowed')
        if not payload.get('orderLinkId') or len(str(payload.get('orderLinkId'))) > 36:
            raise ValueError('invalid_orderLinkId')
        if not payload.get('qty'):
            raise ValueError('qty_required')
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
            'closeOnTrigger': True,
            'orderLinkId': order_link_id,
        }
        return self.place_order(payload)

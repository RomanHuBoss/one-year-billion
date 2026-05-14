from __future__ import annotations
from dataclasses import dataclass, field
import json
from typing import Any


def _safe_repository_call(reasons: list[str], data: dict[str, Any], check_name: str, reason_code: str, func, default):
    """Выполняет DB/evidence check без traceback в операторском интерфейсе.

    Если PostgreSQL доступен, но migrations еще не применены, preflight должен
    вернуть понятный BLOCKED с причиной, а не падать stack trace-ом.
    Это особенно важно для первого запуска, когда оператор сначала видит
    testnet/live preflight, а только потом применяет migrations из UI.
    """

    try:
        return func()
    except Exception as exc:  # pragma: no cover - зависит от внешней БД и версии schema.
        reasons.append(reason_code)
        data[f'{check_name}_error'] = f'{type(exc).__name__}:{exc}'
        return default
from app.core.settings import Settings
from app.execution.bybit_adapter import BybitAdapter, BybitConfig, BybitAPIError


@dataclass
class PreflightResult:
    status: str
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == 'ok' and not self.reasons and all(self.checks.values())


def _api_key_permissions_allow_linear_trade(payload: dict[str, Any]) -> bool:
    """Best-effort parser for Bybit API-key permissions.

    Формат permissions может отличаться по account mode/API generation. Поэтому
    parser не ищет точное поле, а требует признаков contract/derivatives и
    trade/order permission. Если формат неизвестен — fail-closed.
    """

    text = json.dumps(payload.get('result') or payload, ensure_ascii=False, sort_keys=True).lower()
    has_contract_scope = any(token in text for token in ('contracttrade', 'contract_trade', 'derivatives', 'linear'))
    has_trade_scope = any(token in text for token in ('trade', 'order', 'write'))
    return has_contract_scope and has_trade_scope


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _extract_runtime_specs(item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Извлекает обязательные runtime-параметры инструмента Bybit V5.

    Live-preflight не должен ограничиваться status=Trading: tickSize, qtyStep,
    minQty/minNotional и maxLeverage влияют на sizing и risk. Если Bybit меняет
    формат ответа или поле отсутствует, preflight fail-closed блокирует live.
    """

    lot = item.get('lotSizeFilter') or {}
    price = item.get('priceFilter') or {}
    leverage = item.get('leverageFilter') or {}
    extracted = {
        'symbol': item.get('symbol'),
        'category': item.get('category', 'linear'),
        'status': item.get('status'),
        'tick_size': price.get('tickSize'),
        'qty_step': lot.get('qtyStep'),
        'min_qty': lot.get('minOrderQty'),
        'min_notional': lot.get('minNotionalValue'),
        'max_leverage': leverage.get('maxLeverage'),
    }
    missing = [
        field for field in ('tick_size', 'qty_step', 'min_qty', 'min_notional', 'max_leverage')
        if not _positive_number(extracted.get(field))
    ]
    return extracted, missing


def build_adapter(settings: Settings) -> BybitAdapter:
    return BybitAdapter(BybitConfig(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        testnet=settings.bybit_testnet,
        trading_enabled=settings.trading_enabled,
        live_confirm=settings.bybit_live_confirm,
        recv_window_ms=settings.bybit_recv_window_ms,
        time_sync_ttl_sec=settings.bybit_time_sync_ttl_sec,
        time_safety_margin_ms=settings.bybit_time_safety_margin_ms,
    ))



def _safe_bybit_error(exc: Exception) -> dict[str, Any]:
    """Возвращает безопасную для UI диагностику без ключей/секретов."""

    if isinstance(exc, BybitAPIError):
        return exc.safe_dict()
    return {
        'code': type(exc).__name__,
        'ret_code': None,
        'ret_msg': str(exc),
        'path': None,
        'http_status': None,
    }


def _bybit_reason(prefix: str, exc: Exception) -> str:
    if isinstance(exc, BybitAPIError):
        return f'{prefix}:{exc.reason_code()}'
    return f'{prefix}:{type(exc).__name__}'


def _operator_hint_for_bybit_private_errors(errors: list[dict[str, Any]]) -> list[str]:
    """Конкретные действия оператора при падении private API.

    Public API может работать, а private API — нет. В этом случае проблема почти
    всегда в ключах/секрете, endpoint testnet/live, IP whitelist или permission.
    """

    if not errors:
        return []
    hints = [
        'Проверьте, что BYBIT_TESTNET=true и ключи созданы именно в Bybit testnet, а не в live-кабинете.',
        'Проверьте BYBIT_API_KEY/BYBIT_API_SECRET: без пробелов, переносов строк и кавычек в .env.',
        'Проверьте IP whitelist ключа Bybit: текущий IP/VPS должен быть разрешен.',
        'Проверьте права ключа: для Linear USDT Futures нужны contract/derivatives trade/order permissions.',
        'После исправления перезапустите backend и повторите Testnet preflight.',
    ]
    if any(str(err.get('ret_code')) == '10002' or err.get('code') == 'bybit_timestamp_window_error' for err in errors):
        hints.insert(0, 'retCode=10002 означает не плохой ключ, а рассинхрон времени/recv_window. Backend теперь синхронизирует подпись с Bybit server time; если ошибка повторяется, включите синхронизацию часов Windows и повторите preflight.')
    if any(str(err.get('ret_code')) in {'10003', '10004', '10005', '10007'} for err in errors):
        hints.insert(0, 'retCode похож на проблему ключа/подписи/permissions: чаще всего перепутаны testnet/live keys или неверный secret.')
    return hints


def _try_wallet_balance(adapter: BybitAdapter) -> tuple[dict[str, Any], str]:
    """Проверяет wallet-balance с fallback UNIFIED -> CONTRACT.

    На разных testnet-аккаунтах Bybit accountType может отличаться. Preflight не
    должен скрывать это как RuntimeError, поэтому пробуем безопасный fallback и
    возвращаем использованный account_type.
    """

    first_error: Exception | None = None
    for account_type in ('UNIFIED', 'CONTRACT'):
        try:
            return adapter.get_wallet_balance(account_type=account_type), account_type
        except TypeError as exc:
            # Некоторые test doubles из старых тестов реализуют метод без
            # keyword-аргумента. Это не должно ломать production helper.
            if 'account_type' in str(exc):
                return adapter.get_wallet_balance(), 'UNIFIED'
            if first_error is None:
                first_error = exc
        except Exception as exc:  # pragma: no cover - зависит от внешнего Bybit account mode.
            if first_error is None:
                first_error = exc
    assert first_error is not None
    raise first_error

def _run_bybit_runtime_checks(settings: Settings, runtime, reasons: list[str], checks: dict[str, bool], data: dict[str, Any], adapter: BybitAdapter | None = None) -> None:
    """Проверяет Bybit runtime без отправки ордеров."""

    adapter = adapter or build_adapter(settings)
    try:
        if hasattr(adapter, 'sync_time'):
            server = adapter.sync_time()
            if hasattr(adapter, 'time_sync_status'):
                data['bybit_time_sync'] = adapter.time_sync_status()
        else:
            server = adapter.get_server_time()
        data['bybit_server_time'] = server.get('time') or server.get('result')
        checks['bybit_public_api_reachable'] = True
    except Exception as exc:
        checks['bybit_public_api_reachable'] = False
        reasons.append(f'bybit_public_api_unreachable:{type(exc).__name__}')

    runtime_specs: dict[str, Any] = {}
    runtime_spec_reasons: list[str] = []
    for symbol in runtime.live_universe:
        try:
            info = adapter.runtime_instruments_info(symbol)
            item = (info.get('result') or {}).get('list', [{}])[0]
            extracted, missing = _extract_runtime_specs(item)
            runtime_specs[symbol] = extracted
            if item.get('symbol') != symbol or item.get('category', 'linear') != 'linear' or item.get('status') != 'Trading':
                runtime_spec_reasons.append(f'{symbol}:runtime_specs_not_tradable_linear')
            if missing:
                runtime_spec_reasons.append(f'{symbol}:runtime_specs_missing_or_nonpositive:{",".join(missing)}')
        except Exception as exc:
            runtime_spec_reasons.append(f'{symbol}:runtime_specs_check_failed:{type(exc).__name__}')
    reasons.extend(runtime_spec_reasons)
    checks['runtime_instrument_specs_verified'] = not runtime_spec_reasons
    data['runtime_specs'] = runtime_specs

    private_errors: list[dict[str, Any]] = []
    key_info: dict[str, Any] | None = None
    try:
        key_info = adapter.get_api_key_info()
        checks['bybit_private_api_verified'] = True
        data['bybit_private_auth_check'] = 'ok'
    except Exception as exc:
        checks['bybit_private_api_verified'] = False
        error = _safe_bybit_error(exc)
        error['check'] = 'query_api_key'
        private_errors.append(error)
        reasons.append(_bybit_reason('bybit_private_api_auth_failed', exc))

    if key_info is not None:
        checks['bybit_api_key_trade_permission_verified'] = _api_key_permissions_allow_linear_trade(key_info)
        if not checks['bybit_api_key_trade_permission_verified']:
            reasons.append('bybit_api_key_trade_permission_not_verified')
    else:
        checks['bybit_api_key_trade_permission_verified'] = False

    try:
        account, account_type = _try_wallet_balance(adapter)
        data['account_runtime_check'] = 'ok'
        data['account_mode_checked'] = account_type
        data['account_mode_hint'] = (account.get('result') or {}).get('list', [{}])[0].get('accountType') if account.get('result') else account_type
        checks['bybit_wallet_balance_verified'] = True
    except Exception as exc:
        checks['bybit_wallet_balance_verified'] = False
        error = _safe_bybit_error(exc)
        error['check'] = 'wallet_balance'
        private_errors.append(error)
        reasons.append(_bybit_reason('bybit_wallet_balance_failed', exc))

    try:
        positions = adapter.get_positions()
        data['positions_runtime_check'] = 'ok' if positions.get('result') is not None else 'unknown'
        checks['bybit_positions_verified'] = positions.get('result') is not None
        if not checks['bybit_positions_verified']:
            reasons.append('bybit_positions_response_without_result')
    except Exception as exc:
        checks['bybit_positions_verified'] = False
        error = _safe_bybit_error(exc)
        error['check'] = 'position_list'
        private_errors.append(error)
        reasons.append(_bybit_reason('bybit_positions_failed', exc))

    checks['bybit_private_api_and_permissions_verified'] = (
        checks.get('bybit_private_api_verified')
        and checks.get('bybit_api_key_trade_permission_verified')
        and checks.get('bybit_wallet_balance_verified')
        and checks.get('bybit_positions_verified')
    )
    if hasattr(adapter, 'time_sync_status'):
        data['bybit_time_sync'] = adapter.time_sync_status()
    if private_errors:
        data['bybit_private_errors'] = private_errors
        data['operator_private_api_hint'] = _operator_hint_for_bybit_private_errors(private_errors)


def _check_unresolved_incidents(settings: Settings, repository, reasons: list[str], checks: dict[str, bool], data: dict[str, Any]) -> None:
    if repository is not None:
        open_high = _safe_repository_call(
            reasons,
            data,
            'unresolved_critical_high',
            'incidents_table_missing_or_migrations_not_applied',
            repository.unresolved_critical_high,
            default=None,
        )
        if open_high is None:
            checks['unresolved_critical_high_zero'] = False
            data['unresolved_critical_high_count'] = None
        else:
            checks['unresolved_critical_high_zero'] = len(open_high) == 0
            data['unresolved_critical_high_count'] = len(open_high)
            if open_high:
                reasons.append('unresolved_critical_high_incidents')
    else:
        checks['unresolved_critical_high_zero'] = not settings.require_db_for_live
        if settings.require_db_for_live:
            reasons.append('cannot_verify_unresolved_incidents_without_db')


def run_live_preflight(
    settings: Settings,
    runtime,
    db_available: bool,
    repository=None,
    adapter: BybitAdapter | None = None,
    mode: str = 'live',
) -> PreflightResult:
    """Fail-closed runtime gate for testnet/live.

    mode='testnet' проверяет testnet readiness без live-submit и Go/No-Go gates.
    mode='live' оставляет строгий live gate: DB + Bybit runtime + paper evidence + Go/No-Go.
    Ни один режим не отправляет ордера.
    """

    normalized_mode = 'testnet' if mode == 'testnet' else 'live'
    reasons: list[str] = []
    checks: dict[str, bool] = {}
    data: dict[str, Any] = {
        'exchange_scope': 'bybit_v5_linear_usdt_only',
        'phase': runtime.phase,
        'config_hash': runtime.config_hash,
        'live_universe': runtime.live_universe,
        'preflight_mode': normalized_mode,
    }

    if normalized_mode == 'testnet':
        checks['testnet_endpoint_selected'] = bool(settings.bybit_testnet)
        checks['demo_mode_off'] = not settings.demo_mode
        checks['demo_ml_override_off'] = not settings.allow_demo_ml
        checks['database_available'] = bool(db_available) if settings.require_db_for_live else True
        checks['testnet_credentials_present'] = bool(settings.bybit_api_key and settings.bybit_api_secret)
        data['live_submit_required'] = False
        data['go_no_go_required_for_testnet'] = False

        if not checks['testnet_endpoint_selected']:
            reasons.append('testnet_endpoint_not_selected')
        if not checks['demo_mode_off']:
            reasons.append('demo_mode_forbidden_for_testnet_preflight')
        if not checks['demo_ml_override_off']:
            reasons.append('demo_ml_override_forbidden_for_testnet_preflight')
        if not checks['database_available']:
            reasons.append('database_required_for_testnet_preflight')
        _check_unresolved_incidents(settings, repository, reasons, checks, data)

        if not checks['testnet_credentials_present']:
            reasons.append('testnet_bybit_credentials_missing')
        else:
            _run_bybit_runtime_checks(settings, runtime, reasons, checks, data, adapter)

        status = 'ok' if not reasons and all(checks.values()) else 'blocked'
        return PreflightResult(status=status, reasons=sorted(set(reasons)), checks=checks, data=data)

    # Строгий live gate. Эти проверки не применяются к testnet preflight.
    checks['live_submit_explicitly_enabled'] = bool(settings.enable_live_submit)
    checks['trading_flags_confirmed'] = bool(settings.trading_enabled and settings.bybit_live_confirm and settings.bybit_api_key and settings.bybit_api_secret)
    checks['demo_mode_off'] = not settings.demo_mode
    checks['demo_ml_override_off'] = not settings.allow_demo_ml
    checks['database_available'] = bool(db_available) if settings.require_db_for_live else True
    go_no_go_env_approved = bool(settings.live_go_nogo_passed and settings.live_approved_by) if settings.require_go_nogo_for_live else True
    checks['go_no_go_env_approved'] = go_no_go_env_approved

    if not checks['live_submit_explicitly_enabled']:
        reasons.append('cas_enable_live_submit_false')
    if not checks['trading_flags_confirmed']:
        reasons.append('trading_flags_or_bybit_credentials_missing')
    if not checks['demo_mode_off']:
        reasons.append('demo_mode_forbidden_for_live')
    if not checks['demo_ml_override_off']:
        reasons.append('demo_ml_override_forbidden_for_live')
    if not checks['database_available']:
        reasons.append('database_required_for_live')
    if not checks['go_no_go_env_approved']:
        reasons.append('go_no_go_pass_and_approver_required')

    _check_unresolved_incidents(settings, repository, reasons, checks, data)

    if settings.require_go_nogo_for_live:
        if repository is not None and hasattr(repository, 'live_evidence_status'):
            evidence_result = _safe_repository_call(
                reasons,
                data,
                'go_no_go_evidence',
                'go_no_go_tables_missing_or_migrations_not_applied',
                lambda: repository.live_evidence_status(settings.min_paper_days_required, runtime.config_hash),
                default=None,
            )
            if evidence_result is None:
                evidence_ok, evidence_reasons, evidence_data = False, [], {'schema_ready': False}
            else:
                evidence_ok, evidence_reasons, evidence_data = evidence_result
            checks['go_no_go_evidence_verified'] = evidence_ok
            data['go_no_go_evidence'] = evidence_data
            reasons.extend(evidence_reasons)
        else:
            checks['go_no_go_evidence_verified'] = False
            reasons.append('go_no_go_evidence_db_required')
        checks['go_no_go_approved'] = checks['go_no_go_env_approved'] and checks['go_no_go_evidence_verified']
    else:
        checks['go_no_go_evidence_verified'] = True
        checks['go_no_go_approved'] = True

    if settings.require_live_preflight and checks['trading_flags_confirmed']:
        _run_bybit_runtime_checks(settings, runtime, reasons, checks, data, adapter)

    status = 'ok' if not reasons and all(checks.values()) else 'blocked'
    return PreflightResult(status=status, reasons=sorted(set(reasons)), checks=checks, data=data)

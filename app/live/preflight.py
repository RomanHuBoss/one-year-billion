from __future__ import annotations
from dataclasses import dataclass, field
import json
from typing import Any
from app.core.settings import Settings
from app.execution.bybit_adapter import BybitAdapter, BybitConfig


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
    ))


def run_live_preflight(settings: Settings, runtime, db_available: bool, repository=None, adapter: BybitAdapter | None = None) -> PreflightResult:
    """Fail-closed runtime gate before live submit.

    Без реального Bybit-аккаунта этот check законно вернет BLOCKED. Это не баг:
    спецификация требует подтверждать внешние параметры runtime перед
    trading_enabled=true, а не доверять .env и YAML.
    """

    reasons: list[str] = []
    checks: dict[str, bool] = {}
    data: dict[str, Any] = {
        'exchange_scope': 'bybit_v5_linear_usdt_only',
        'phase': runtime.phase,
        'config_hash': runtime.config_hash,
        'live_universe': runtime.live_universe,
    }

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

    if repository is not None:
        open_high = repository.unresolved_critical_high()
        checks['unresolved_critical_high_zero'] = len(open_high) == 0
        data['unresolved_critical_high_count'] = len(open_high)
        if open_high:
            reasons.append('unresolved_critical_high_incidents')
    else:
        checks['unresolved_critical_high_zero'] = not settings.require_db_for_live
        if settings.require_db_for_live:
            reasons.append('cannot_verify_unresolved_incidents_without_db')

    if settings.require_go_nogo_for_live:
        if repository is not None and hasattr(repository, 'live_evidence_status'):
            evidence_ok, evidence_reasons, evidence_data = repository.live_evidence_status(settings.min_paper_days_required, runtime.config_hash)
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
        adapter = adapter or build_adapter(settings)
        try:
            server = adapter.get_server_time()
            data['bybit_server_time'] = server.get('time') or server.get('result')
            checks['bybit_public_api_reachable'] = True
        except Exception as exc:
            checks['bybit_public_api_reachable'] = False
            reasons.append(f'bybit_public_api_unreachable:{type(exc).__name__}')

        # Public runtime specs for every live symbol.
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

        # Authenticated check confirms that keys/permissions are not fake strings.
        try:
            account = adapter.get_wallet_balance()
            positions = adapter.get_positions()
            key_info = adapter.get_api_key_info()
            data['account_runtime_check'] = 'ok'
            data['account_mode_hint'] = (account.get('result') or {}).get('list', [{}])[0].get('accountType') if account.get('result') else None
            data['positions_runtime_check'] = 'ok' if positions.get('result') is not None else 'unknown'
            checks['bybit_private_api_verified'] = True
            checks['bybit_api_key_trade_permission_verified'] = _api_key_permissions_allow_linear_trade(key_info)
            if not checks['bybit_api_key_trade_permission_verified']:
                reasons.append('bybit_api_key_trade_permission_not_verified')
            checks['bybit_private_api_and_permissions_verified'] = checks['bybit_private_api_verified'] and checks['bybit_api_key_trade_permission_verified']
        except Exception as exc:
            checks['bybit_private_api_verified'] = False
            checks['bybit_api_key_trade_permission_verified'] = False
            checks['bybit_private_api_and_permissions_verified'] = False
            reasons.append(f'bybit_private_api_or_permissions_failed:{type(exc).__name__}')

    status = 'ok' if not reasons and all(checks.values()) else 'blocked'
    return PreflightResult(status=status, reasons=sorted(set(reasons)), checks=checks, data=data)

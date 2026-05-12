from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import request_id
from app.live.preflight import run_live_preflight
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read

router = APIRouter(prefix='/api/operator', tags=['operator'])

STATUS_LABELS = {
    'ACTIVE': 'Активна и защищена',
    'NO_TRADE': 'Сделок нет',
    'PENDING': 'Ожидает проверки',
    'BLOCKED': 'Заблокировано',
    'DE_RISK': 'Снижение риска',
    'ERROR_RECONCILIATION_REQUIRED': 'Нужна сверка с биржей',
    'CLOSED': 'Закрыто',
}

REASON_LABELS = {
    'waiting_for_risk_approved_signal': 'Ожидаем сигнал, который пройдет ML/risk-gate',
    'missing_instrument_specs': 'Нет спецификаций инструмента',
    'stale_instrument_specs': 'Спецификации инструмента устарели',
    'missing_market_snapshot': 'Нет свежего снимка рынка',
    'stale_market': 'Рыночные данные устарели',
    'database_required_for_live': 'Для live нужна PostgreSQL-БД',
    'database_required_for_live_risk_approval': 'Risk approval в live требует PostgreSQL',
    'go_no_go_evidence_db_required': 'Go/No-Go evidence должен быть записан в БД',
    'go_no_go_pass_and_approver_required': 'Нужен подписанный Go/No-Go PASS',
    'cas_enable_live_submit_false': 'Live-submit явно выключен',
    'trading_flags_or_bybit_credentials_missing': 'Не заданы live-флаги или ключи Bybit',
    'cannot_verify_unresolved_incidents_without_db': 'Без БД нельзя проверить CRITICAL/HIGH incidents',
}

ACTION_INFO = {
    'DISABLE_TRADING': {
        'title': 'Отключить торговлю',
        'description': 'Безопасно выключает новые входы. Используйте при сомнениях, ошибках данных или нестабильности биржи.',
    },
    'CANCEL_OPEN_ENTRIES': {
        'title': 'Отменить входные заявки',
        'description': 'Отменяет открытые входы, не увеличивает позицию и не меняет плечо.',
    },
    'FLATTEN_REDUCE': {
        'title': 'Снизить / закрыть риск',
        'description': 'Переводит систему в reduce-only логику для уменьшения позиции.',
    },
    'RESOLVE_INCIDENT': {
        'title': 'Закрыть инцидент',
        'description': 'Только после ручной проверки причины, сверки биржи и подтверждения состояния.',
    },
}


def _reason_to_text(reason: str) -> str:
    if reason in REASON_LABELS:
        return REASON_LABELS[reason]
    if ':' in reason:
        head, tail = reason.split(':', 1)
        return f'{REASON_LABELS.get(head, head)}: {tail}'
    return reason.replace('_', ' ')


def _status_to_label(status: str) -> str:
    return STATUS_LABELS.get(status, status.replace('_', ' '))


def _level_from_status(status: str, severity: str | None = None) -> str:
    normalized = (status or '').lower()
    sev = (severity or '').lower()
    if normalized == 'ok' or sev in {'ok', 'success'}:
        return 'ok'
    if normalized in {'blocked', 'rejected'} or sev in {'high', 'critical'}:
        return 'danger'
    if sev in {'medium', 'warning'} or normalized in {'warning', 'pending'}:
        return 'warning'
    return 'info'


def _runtime_result(request: Request):
    settings = request.app.state.settings
    runtime = request.app.state.runtime_config
    if settings.live_requested:
        return run_live_preflight(
            settings=settings,
            runtime=runtime,
            db_available=bool(getattr(request.app.state, 'db_available', False)),
            repository=getattr(request.app.state, 'repository', None),
        )

    state = request.app.state.demo_state
    reasons: list[str] = []
    for symbol in runtime.live_universe:
        specs = state.specs.get(symbol)
        market = state.market.get(symbol)
        if specs is None or not specs.fresh:
            reasons.append(f'{symbol}:stale_or_missing_specs')
        if market is None or not market.fresh:
            reasons.append(f'{symbol}:stale_or_missing_market')

    class LocalResult:
        pass

    result = LocalResult()
    result.status = 'ok' if not reasons else 'blocked'
    result.checks = {
        'local_runtime_data_fresh': not reasons,
        'live_submit_disabled': True,
        'frontend_source_backend': True,
    }
    result.data = {
        'mode': 'local_smoke',
        'phase': runtime.phase,
        'config_hash': runtime.config_hash,
        'exchange_scope': 'bybit_v5_linear_usdt_only',
    }
    result.ok = result.status == 'ok'
    result.reasons = reasons
    return result


def _symbol_rows(request: Request) -> list[dict[str, Any]]:
    repo = getattr(request.app.state, 'repository', None)
    if repo is not None:
        rows = repo.latest_statuses()
    else:
        rows = request.app.state.demo_state.overview()
    enriched: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get('status_effective', 'UNKNOWN'))
        reasons = list(row.get('reasons') or [])
        severity = str(row.get('severity', 'info'))
        allowed = list(row.get('allowed_actions') or [])
        enriched.append({
            **row,
            'status_label': _status_to_label(status),
            'severity_level': _level_from_status(status, severity),
            'reason_labels': [_reason_to_text(r) for r in reasons],
            'operator_hint': _symbol_hint(status, reasons),
            'allowed_action_labels': [ACTION_INFO.get(a, {'title': a})['title'] for a in allowed],
        })
    return enriched


def _symbol_hint(status: str, reasons: list[str]) -> str:
    if status == 'ACTIVE':
        return 'Наблюдать защиту позиции: reconciliation должен быть PASS, protection_state=VALID.'
    if status == 'ERROR_RECONCILIATION_REQUIRED':
        return 'Не открывать новые заявки. Сначала сверить биржу, затем reduce-only/flatten при необходимости.'
    if status in {'BLOCKED', 'DE_RISK'}:
        return 'Не пытаться обходить блокировку. Исправить причины и повторить preflight.'
    if 'waiting_for_risk_approved_signal' in reasons:
        return 'Это нормальное состояние: система ждет качественный сигнал и не торгует без risk approval.'
    return 'Проверить причины, затем действовать только через разрешенные safe-actions.'


def _readiness_cards(request: Request, runtime_result) -> list[dict[str, str]]:
    settings = request.app.state.settings
    runtime = request.app.state.runtime_config
    db_available = bool(getattr(request.app.state, 'db_available', False))
    checks = getattr(runtime_result, 'checks', {}) or {}
    return [
        {
            'id': 'trading',
            'title': 'Торговля',
            'value': 'выключена' if not settings.trading_enabled else 'запрошена',
            'state': 'ok' if not settings.trading_enabled else 'warning',
            'hint': 'По умолчанию новые live-ордера невозможны.',
        },
        {
            'id': 'database',
            'title': 'База данных',
            'value': 'подключена' if db_available else 'нет подключения',
            'state': 'ok' if db_available else 'warning',
            'hint': 'Для live PostgreSQL обязателен: constraints, idempotency, audit, Go/No-Go evidence.',
        },
        {
            'id': 'risk',
            'title': 'Risk engine',
            'value': 'жесткий gate',
            'state': 'ok',
            'hint': 'Нет approved non-expired risk_decision_id - нет order.',
        },
        {
            'id': 'live_gate',
            'title': 'Live gate',
            'value': 'PASS' if runtime_result.status == 'ok' and settings.can_live_trade else 'закрыт',
            'state': 'ok' if runtime_result.status == 'ok' and settings.can_live_trade else 'danger',
            'hint': 'Live запрещен до DB, Bybit runtime, paper evidence и Go/No-Go PASS.',
        },
        {
            'id': 'phase',
            'title': 'Фаза и символы',
            'value': f'Phase {runtime.phase}: ' + ', '.join(runtime.live_universe),
            'state': 'info',
            'hint': 'Phase 0: только BTCUSDT, ETHUSDT, SOLUSDT после runtime-проверок.',
        },
        {
            'id': 'ml',
            'title': 'ML',
            'value': 'фильтр, не трейдер',
            'state': 'ok' if not settings.allow_demo_ml else 'warning',
            'hint': 'ML может только ALLOW/BLOCK/UNAVAILABLE; stale/missing model fail-closed.',
        },
    ]


def _operator_steps(request: Request, runtime_result) -> list[dict[str, str]]:
    settings = request.app.state.settings
    checks = getattr(runtime_result, 'checks', {}) or {}
    db_available = bool(getattr(request.app.state, 'db_available', False))
    return [
        {
            'id': 'validate',
            'title': '1. Локальная проверка кода',
            'state': 'manual',
            'command': 'python main.py validate',
            'explain': 'Должны пройти pytest, architecture checks, migration checks и secret scan.',
            'pass_when': 'Команда завершилась без ошибок.',
        },
        {
            'id': 'testnet_preflight',
            'title': '2. Testnet preflight',
            'state': 'manual',
            'command': 'python main.py preflight --mode testnet',
            'explain': 'Проверяет настройки, Bybit testnet, runtime specs и безопасные блокировки без реальных денег.',
            'pass_when': 'status=ok. Если blocked - исправить reasons.',
        },
        {
            'id': 'postgresql',
            'title': '3. PostgreSQL и миграции',
            'state': 'ok' if db_available else 'todo',
            'command': './scripts/bootstrap_db.sh',
            'explain': 'БД хранит hard constraints, idempotency, risk decisions, fills, incidents и evidence.',
            'pass_when': 'database_available=true в Runtime-проверке.',
        },
        {
            'id': 'paper_shadow',
            'title': '4. Paper/shadow 14+ дней',
            'state': 'ok' if checks.get('go_no_go_evidence_verified') else 'todo',
            'command': 'python scripts/record_go_no_go_evidence.py --type PHASE0_PAPER --status PASS ...',
            'explain': 'Нужно накопить evidence без unresolved incidents и с reconciliation PASS.',
            'pass_when': 'Evidence записан в PostgreSQL и проходит live preflight.',
        },
        {
            'id': 'go_no_go',
            'title': '5. Go/No-Go PASS',
            'state': 'ok' if checks.get('go_no_go_approved') else 'todo',
            'command': 'python scripts/record_go_no_go_evidence.py --type GO_NO_GO --status PASS --approved-by <owner>',
            'explain': 'Финальное решение владельца продукта после CI, security, paper/shadow и reconciliation evidence.',
            'pass_when': 'go_no_go_approved=true.',
        },
        {
            'id': 'live_preflight',
            'title': '6. Live preflight',
            'state': 'ok' if runtime_result.status == 'ok' and settings.can_live_trade else 'blocked',
            'command': 'python main.py preflight --mode live',
            'explain': 'До PASS live-submit должен оставаться закрытым. blocked - безопасное состояние.',
            'pass_when': 'status=ok, все checks=true, unresolved CRITICAL/HIGH=0.',
        },
    ]


def _top_banner(request: Request, runtime_result) -> dict[str, str]:
    settings = request.app.state.settings
    if runtime_result.status == 'ok' and settings.can_live_trade:
        return {
            'level': 'ok',
            'title': 'Live gate открыт технически',
            'message': 'Перед каждым ордером все равно требуются approved RiskDecision, idempotency и protection/reconciliation.',
            'next_step': 'Работать строго по runbook: без ручных risk-up действий и без повторного submit с новым idempotency key.',
        }
    if settings.live_requested:
        return {
            'level': 'danger',
            'title': 'Live заблокирован',
            'message': 'Система видит live-настройки, но один или несколько gate не пройдены. Это правильное fail-closed поведение.',
            'next_step': 'Откройте блок "Что мешает запуску" и исправляйте причины сверху вниз.',
        }
    return {
        'level': 'ok',
        'title': 'Безопасный локальный режим',
        'message': 'Реальные ордера не отправляются. Можно тестировать интерфейс, paper-конвейер и локальные проверки.',
        'next_step': 'Запустите "Paper один раз", затем выполните python main.py validate и testnet preflight.',
    }


def _safe_actions(symbols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = sorted({action for row in symbols for action in row.get('allowed_actions', [])})
    return [
        {
            'action': action,
            'title': ACTION_INFO.get(action, {'title': action})['title'],
            'description': ACTION_INFO.get(action, {'description': 'Разрешенное действие backend.'})['description'],
            'requires_reason': True,
            'requires_operator_key': True,
            'risk_direction': 'only_decrease_or_neutral',
        }
        for action in allowed if action in ACTION_INFO
    ]


@router.get('/dashboard')
async def operator_dashboard(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    runtime = request.app.state.runtime_config
    settings = request.app.state.settings
    runtime_result = _runtime_result(request)
    symbols = _symbol_rows(request)
    reasons = sorted(set(getattr(runtime_result, 'reasons', []) or []))
    data = {
        'source_of_truth': 'backend_status_effective',
        'app': settings.app_name,
        'version': 'operator-module-v2',
        'operator_mode': 'live_requested' if settings.live_requested else 'local_or_testnet_safe',
        'hero': _top_banner(request, runtime_result),
        'cards': _readiness_cards(request, runtime_result),
        'steps': _operator_steps(request, runtime_result),
        'symbols': symbols,
        'safe_actions': _safe_actions(symbols),
        'blockers': [
            {'code': reason, 'text': _reason_to_text(reason), 'level': 'danger'}
            for reason in reasons
        ],
        'limits': {
            'phase': runtime.phase,
            'universe': runtime.live_universe,
            'live_strategies': runtime.live_strategies,
            'shadow_strategies': runtime.shadow_strategies,
            'risk_pct_default': runtime.risk.risk_pct_default,
            'risk_pct_absolute_max': float((runtime.raw.get('risk.yaml') or {}).get('risk_pct_absolute_max', (runtime.raw.get('account_phase.yaml') or {}).get('risk_pct_absolute_max', runtime.risk.risk_pct_default))),
            'max_effective_leverage': runtime.risk.max_effective_leverage,
            'approval_ttl_seconds': runtime.risk.approval_ttl_seconds,
            'turnover_round_turns_per_day': int((runtime.raw.get('risk.yaml') or {}).get('turnover_round_turns_per_day', 4)),
        },
        'diagnostics': {
            'runtime_status': runtime_result.status,
            'runtime_checks': getattr(runtime_result, 'checks', {}),
            'runtime_data': getattr(runtime_result, 'data', {}),
            'runtime_reasons': reasons,
            'database_available': bool(getattr(request.app.state, 'db_available', False)),
            'live_order_submit_enabled': runtime_result.status == 'ok' and settings.can_live_trade,
            'frontend_source_of_truth': 'backend_status_effective',
        },
    }
    status = 'ok' if runtime_result.status == 'ok' else 'blocked'
    return ApiEnvelope(request_id=rid, status=status, reasons=reasons, data=data)

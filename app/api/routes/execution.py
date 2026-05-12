from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.schemas.domain import RiskDecision, SignalCandidate
from app.security.auth import require_operator
from app.execution.bybit_adapter import BybitAdapter, BybitConfig
from app.live.gate import assert_live_submit_allowed

router = APIRouter(prefix='/api/execution', tags=['execution'])


def _parse_execution_payload(payload: dict) -> tuple[SignalCandidate, RiskDecision]:
    try:
        signal = SignalCandidate(**payload['signal'])
        risk = RiskDecision(**payload['risk_decision'])
        return signal, risk
    except (KeyError, TypeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=f'invalid_execution_payload:{type(exc).__name__}') from exc


@router.post('/paper-submit')
async def paper_submit(
    payload: dict,
    request: Request,
    rid: str = Depends(request_id),
    actor: str = Depends(require_operator),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
) -> ApiEnvelope:
    signal, risk = _parse_execution_payload(payload)
    idem = x_idempotency_key or payload.get('idempotency_key')
    if not idem:
        raise HTTPException(status_code=400, detail='idempotency_key_required')
    router_service = request.app.state.order_router
    intent = router_service.build_intent(signal, risk, idem)
    settings = request.app.state.settings
    # Endpoint remains paper-only. Live execution uses /api/execution/live-submit.
    adapter = BybitAdapter(BybitConfig(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_testnet, False, False))
    ack = adapter.place_order(router_service.bybit_payload(intent))
    return ApiEnvelope(request_id=rid, trace_id=signal.trace_id, status='ok', data={'intent': intent.model_dump(mode='json'), 'exchange_ack': ack, 'mode': 'paper', 'actor': actor})


@router.post('/live-submit')
async def live_submit(
    payload: dict,
    request: Request,
    rid: str = Depends(request_id),
    actor: str = Depends(require_operator),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
) -> ApiEnvelope:
    """Go/No-Go gated live entry submit.

    Этот route существует, но fail-closed: без DB, runtime preflight, approved
    persisted RiskDecision and explicit CAS_ENABLE_LIVE_SUBMIT=true он вернет 423.
    """

    gate = assert_live_submit_allowed(request)
    signal, risk = _parse_execution_payload(payload)
    idem = x_idempotency_key or payload.get('idempotency_key')
    if not idem:
        raise HTTPException(status_code=400, detail='idempotency_key_required')

    repo = getattr(request.app.state, 'repository', None)
    if repo is None:
        raise HTTPException(status_code=423, detail='database_repository_required_for_live')
    ok, db_reasons = repo.verify_live_risk_decision(risk)
    if not ok:
        raise HTTPException(status_code=423, detail={'risk_decision_db_gate_failed': db_reasons})

    router_service = request.app.state.order_router
    intent = router_service.build_intent(signal, risk, idem)
    settings = request.app.state.settings
    adapter = BybitAdapter(BybitConfig(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_testnet, settings.trading_enabled, settings.bybit_live_confirm))
    bybit_payload = router_service.bybit_payload(intent)

    inserted, existing = repo.reserve_order_intent(intent, bybit_payload)
    if not inserted:
        if existing is None:
            raise HTTPException(status_code=409, detail='idempotency_conflict_without_row')
        if str(existing.get('signal_id')) != signal.signal_id or str(existing.get('risk_decision_id')) != risk.risk_decision_id:
            raise HTTPException(status_code=409, detail='idempotency_key_reused_with_different_order')
        # Важное production-правило: повтор idempotency-key не делает второй
        # вызов Bybit. Оператор получает сохраненное состояние и обязан ждать
        # reconciliation/protection, а не повторять submit.
        return ApiEnvelope(request_id=rid, trace_id=signal.trace_id, status='ok', data={
            'mode': 'live',
            'idempotent_replay': True,
            'stored_order_state': existing.get('state'),
            'client_order_id': existing.get('client_order_id'),
            'exchange_order_id': existing.get('exchange_order_id'),
            'ack_is_fill': False,
            'next_required_state': 'private_ws_or_rest_reconciliation_then_protection_verification',
        })

    try:
        ack = adapter.place_order(bybit_payload)
    except Exception as exc:
        reason = f'{type(exc).__name__}:{exc}'
        repo.mark_order_error(intent.client_order_id, reason)
        repo.create_incident('HIGH', 'LIVE_SUBMIT_FAILED_RECONCILIATION_REQUIRED', 'execution', signal.symbol, {'error': reason, 'client_order_id': intent.client_order_id}, signal.trace_id)
        # Лок не освобождаем: неизвестно, приняла ли биржа order до ошибки.
        # Освобождение возможно только после reconciliation/flatten.
        raise HTTPException(status_code=502, detail={
            'live_submit_uncertain_result': 'reconciliation_required',
            'reason': reason,
            'client_order_id': intent.client_order_id,
        }) from exc
    repo.update_order_submitted(intent.client_order_id, ack)
    return ApiEnvelope(request_id=rid, trace_id=signal.trace_id, status='ok', data={
        'intent': intent.model_dump(mode='json'),
        'exchange_ack': ack,
        'mode': 'live',
        'actor': actor,
        'live_gate': gate,
        'ack_is_fill': False,
        'next_required_state': 'private_ws_or_rest_reconciliation_then_protection_verification',
    })

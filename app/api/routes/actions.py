from __future__ import annotations
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from app.api.dependencies import request_id
from app.core.hashes import new_trace_id
from app.execution.idempotency import namespaced_idempotency_key
from app.schemas.api_contract import ActionRequest, ApiEnvelope, ManualActionResult
from app.security.auth import require_operator

router = APIRouter(prefix='/api/actions', tags=['actions'])

ALLOWED_ACTIONS = {'DISABLE_TRADING','CANCEL_OPEN_ENTRIES','FLATTEN_REDUCE','RESOLVE_INCIDENT','PROPOSE_CONFIG','ACTIVATE_CONFIG'}
CONFIG_ACTIONS = {'PROPOSE_CONFIG', 'ACTIVATE_CONFIG'}
CONFIG_SAFE_RISK_CHANGES = {'same', 'decrease', 'risk_decrease'}
AUDIT_REJECTED_ACTION = 'REJECTED_UNSAFE_ACTION'


@router.post('')
async def action(
    req: ActionRequest,
    request: Request,
    rid: str = Depends(request_id),
    actor: str = Depends(require_operator),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
) -> ApiEnvelope:
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail='idempotency_key_required')
    trace_id = new_trace_id('manual')
    reasons = []
    accepted = True
    if req.action not in ALLOWED_ACTIONS:
        accepted = False
        reasons.append('action_not_allowed')
    if not req.reason:
        accepted = False
        reasons.append('reason_required')
    if req.action in CONFIG_ACTIONS:
        # Config activation/proposal is allowed only when metadata proves that
        # the change cannot increase risk. Real config application still goes
        # through config validator and audit; this API guard prevents an
        # operator override from becoming a hidden risk-up path.
        risk_change = str(req.target.get('risk_change', '')).lower()
        if risk_change not in CONFIG_SAFE_RISK_CHANGES:
            accepted = False
            reasons.append('config_change_must_be_risk_reducing_or_neutral')
        if req.target.get('risk_increase') is True:
            accepted = False
            reasons.append('config_risk_increase_forbidden')
    # No force-open or increase-risk endpoint exists by design.
    idem_key = namespaced_idempotency_key('manual', x_idempotency_key)
    cached = request.app.state.idempotency.get(idem_key)
    if cached:
        return ApiEnvelope(request_id=rid, trace_id=cached['trace_id'], status=cached['status'], reasons=cached['reasons'], data=cached['data'])
    request.app.state.demo_state.manual_actions.append({'actor': actor, 'action': req.action, 'reason': req.reason, 'target': req.target, 'accepted': accepted, 'trace_id': trace_id, 'idempotency_key': x_idempotency_key})
    repo = getattr(request.app.state, 'repository', None)
    if repo is not None:
        # Небезопасную команду сохраняем как audit-marker, а не как исполнимое действие.
        # Это предотвращает 500 на DB CHECK и сохраняет исходную попытку в target.
        # Важно: rejected ACTIVATE_CONFIG/PROPOSE_CONFIG с risk_increase=true нельзя
        # писать как ACTIVATE_CONFIG, потому что DB-инвариант manual_config_change_reduce_only
        # обязан технически запретить любые risk-up config records.
        audit_action = req.action if req.action in ALLOWED_ACTIONS else AUDIT_REJECTED_ACTION
        if not accepted and req.action in CONFIG_ACTIONS:
            audit_action = AUDIT_REJECTED_ACTION
        audit_target = dict(req.target)
        if audit_action == AUDIT_REJECTED_ACTION:
            audit_target['attempted_action'] = req.action
            audit_target['rejection_reasons'] = reasons
        repo.log_manual_action(actor=actor, action=audit_action, reason=req.reason or 'reason_missing', target=audit_target, status='ACCEPTED' if accepted else 'REJECTED', trace_id=trace_id)
    result = ManualActionResult(accepted=accepted, action=req.action, reduce_only=True, reasons=reasons, trace_id=trace_id)
    envelope_payload = {'trace_id': trace_id, 'status': 'ok' if accepted else 'rejected', 'reasons': reasons, 'data': result.model_dump()}
    request.app.state.idempotency.put(idem_key, envelope_payload)
    return ApiEnvelope(request_id=rid, trace_id=trace_id, status=envelope_payload['status'], reasons=reasons, data=result.model_dump())

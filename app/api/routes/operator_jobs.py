from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from app.api.dependencies import request_id
from app.core.hashes import new_trace_id
from app.execution.idempotency import namespaced_idempotency_key
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_operator, require_read

router = APIRouter(prefix='/api/operator', tags=['operator-jobs'])


class OperatorCommandRequest(BaseModel):
    reason: str
    options: dict[str, Any] = Field(default_factory=dict)


def _parse_command_request(body: Any) -> OperatorCommandRequest:
    """Разбирает тело запроса от браузера и внешних клиентов.

    В старой версии frontend терял Content-Type при добавлении x-api-key,
    из-за чего FastAPI видел JSON как обычную строку и возвращал 422.
    API остается безопасным: команда всё равно запускается только по allowlist,
    с OPERATOR_API_KEY, причиной и idempotency key. Но оператор теперь получает
    нормальную обработку даже при text/plain теле запроса.
    """

    try:
        if isinstance(body, OperatorCommandRequest):
            return body
        if isinstance(body, str):
            return OperatorCommandRequest.model_validate_json(body)
        if isinstance(body, dict):
            return OperatorCommandRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail={'error': 'invalid_operator_command_request', 'fields': exc.errors()}) from exc
    raise HTTPException(status_code=400, detail='operator_command_request_must_be_json_object')


@router.get('/commands')
async def list_operator_commands(
    request: Request,
    rid: str = Depends(request_id),
    actor: str = Depends(require_read),
) -> ApiEnvelope:
    runner = request.app.state.operator_jobs
    return ApiEnvelope(
        request_id=rid,
        status='ok',
        data={
            'commands': runner.list_commands(),
            'jobs': runner.list_jobs(limit=10),
            'security_model': 'browser_calls_backend_allowlist_only_no_arbitrary_shell',
            'actor': actor,
        },
    )


@router.post('/commands/{command_id}/run')
async def run_operator_command(
    command_id: str,
    request: Request,
    body: Any = Body(...),
    rid: str = Depends(request_id),
    actor: str = Depends(require_operator),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
) -> ApiEnvelope:
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail='idempotency_key_required')
    req = _parse_command_request(body)
    if not req.reason.strip():
        raise HTTPException(status_code=400, detail='reason_required')

    idem_key = namespaced_idempotency_key('operator-command', x_idempotency_key)
    cached = request.app.state.idempotency.get(idem_key)
    if cached:
        return ApiEnvelope(request_id=rid, trace_id=cached['trace_id'], status=cached['status'], reasons=cached['reasons'], data=cached['data'])

    try:
        job = request.app.state.operator_jobs.start(command_id=command_id, actor=actor, reason=req.reason, options=req.options)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    trace_id = new_trace_id('opcmd')
    repo = getattr(request.app.state, 'repository', None)
    audit_warning = None
    if repo is not None:
        try:
            repo.log_manual_action(
                actor=actor,
                action='RUN_OPERATOR_COMMAND',
                reason=req.reason,
                target={'command_id': command_id, 'job_id': job['job_id'], 'options': job.get('options', {})},
                status='ACCEPTED',
                trace_id=trace_id,
            )
        except Exception as exc:  # Старые БД до 0004 могут еще не знать RUN_OPERATOR_COMMAND.
            audit_warning = f'audit_log_deferred_until_migrations:{type(exc).__name__}'
    data = {'job': job, 'security_model': 'allowlisted_python_command_no_shell', 'audit_warning': audit_warning}
    envelope_payload = {'trace_id': trace_id, 'status': 'accepted', 'reasons': [], 'data': data}
    request.app.state.idempotency.put(idem_key, envelope_payload)
    return ApiEnvelope(request_id=rid, trace_id=trace_id, status='accepted', data=data)


@router.get('/jobs/{job_id}')
async def get_operator_job(
    job_id: str,
    request: Request,
    rid: str = Depends(request_id),
    actor: str = Depends(require_read),
) -> ApiEnvelope:
    job = request.app.state.operator_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='operator_job_not_found')
    return ApiEnvelope(request_id=rid, status=job['status'], data={'job': job, 'actor': actor})

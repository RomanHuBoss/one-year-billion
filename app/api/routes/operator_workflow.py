from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.dependencies import request_id
from app.core.hashes import new_trace_id
from app.execution.idempotency import namespaced_idempotency_key
from app.paper_trading.pipeline import PaperPipeline
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_operator, require_read
from app.db.availability import ensure_database_ready

router = APIRouter(prefix='/api/operator/workflow', tags=['operator-workflow'])

EVIDENCE_TYPES = {'PHASE0_PAPER', 'RECONCILIATION', 'SECURITY', 'CI', 'GO_NO_GO'}


class WorkflowActionRequest(BaseModel):
    reason: str = Field(min_length=3)
    approved_by: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


def _job_status(request: Request, command_id: str) -> dict[str, Any] | None:
    jobs = getattr(request.app.state, 'operator_jobs').list_jobs(limit=50)
    for job in jobs:
        if job.get('command_id') == command_id:
            return job
    return None


def _evidence_rows(request: Request) -> dict[str, Any]:
    repo = getattr(request.app.state, 'repository', None)
    runtime = request.app.state.runtime_config
    if repo is None:
        return {t: None for t in EVIDENCE_TYPES}
    if hasattr(repo, 'evidence_summary'):
        return repo.evidence_summary(runtime.config_hash)
    return {t: None for t in EVIDENCE_TYPES}


def _paper_days(row: dict[str, Any] | None) -> float:
    if not row:
        return 0.0
    try:
        if row.get('status') == 'PASS' and row.get('paper_days') is not None:
            return float(row.get('paper_days'))
        started = row.get('started_at')
        ended = row.get('ended_at') or _now()
        if isinstance(started, str):
            started = datetime.fromisoformat(started.replace('Z', '+00:00'))
        if isinstance(ended, str):
            ended = datetime.fromisoformat(ended.replace('Z', '+00:00'))
        if started:
            return max(0.0, (ended - started).total_seconds() / 86400.0)
    except Exception:
        return 0.0
    return 0.0


def _job_step(command_id: str, title: str, job: dict[str, Any] | None, locked: bool = False) -> tuple[str, list[dict[str, Any]]]:
    if locked:
        return 'locked', [{'title': 'Предыдущие крупные шаги не завершены', 'status': 'locked'}]
    if not job:
        return 'todo', [{'title': 'Команда еще не запускалась из панели', 'status': 'todo'}]
    status = job.get('status')
    if status == 'ok':
        return 'ok', [{'title': f'{title}: PASS', 'status': 'ok'}, {'title': f'job_id: {job.get("job_id")}', 'status': 'info'}]
    if status in {'queued', 'running'}:
        return 'running', [{'title': f'{title}: выполняется', 'status': 'running'}, {'title': f'job_id: {job.get("job_id")}', 'status': 'info'}]
    if status == 'blocked':
        return 'blocked', [{'title': f'{title}: сервер вернул blocked', 'status': 'blocked'}, {'title': 'Откройте результат шага ниже и исправьте причины', 'status': 'blocked'}]
    return 'error', [{'title': f'{title}: ошибка', 'status': 'error'}, {'title': 'Нужно исправить traceback/ошибку и повторить шаг', 'status': 'error'}]


def build_workflow(request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    runtime = request.app.state.runtime_config
    db_state = ensure_database_ready(request.app)
    repo = getattr(request.app.state, 'repository', None)
    db_connection_ok = bool(db_state.get('connection_ok'))
    db_schema_ready = bool(db_state.get('schema_ready'))
    db_ok = db_connection_ok and db_schema_ready
    evidence = _evidence_rows(request) if db_ok else {t: None for t in EVIDENCE_TYPES}

    validate_job = _job_status(request, 'validate')
    testnet_job = _job_status(request, 'preflight_testnet')
    live_job = _job_status(request, 'preflight_live')

    ci_ok = bool(evidence.get('CI') and evidence['CI'].get('status') == 'PASS')
    security_ok = bool(evidence.get('SECURITY') and evidence['SECURITY'].get('status') == 'PASS')
    rec_ok = bool(evidence.get('RECONCILIATION') and evidence['RECONCILIATION'].get('status') == 'PASS')
    paper_row = evidence.get('PHASE0_PAPER')
    paper_pass = bool(paper_row and paper_row.get('status') == 'PASS')
    paper_started = bool(paper_row)
    paper_days = _paper_days(paper_row)
    go_ok = bool(evidence.get('GO_NO_GO') and evidence['GO_NO_GO'].get('status') == 'PASS')
    testnet_ok = bool(testnet_job and testnet_job.get('status') == 'ok')
    validate_ok = bool(validate_job and validate_job.get('status') == 'ok') or ci_ok

    live_preflight_state = 'ok' if (live_job and live_job.get('status') == 'ok' and settings.can_live_trade) else 'blocked'

    steps: list[dict[str, Any]] = []
    steps.append({
        'id': 'db',
        'n': 1,
        'title': 'База данных и миграции',
        'goal': 'Поднять PostgreSQL и применить migrations без терминала.',
        'status': 'ok' if db_ok else 'todo',
        'operator_text': 'Нажмите кнопку, если БД не подключена или миграции не применены.',
        'action_id': None if db_ok else 'run_bootstrap_db',
        'primary_button': None if db_ok else 'Применить migrations',
        'substeps': [
            {'title': 'PostgreSQL доступен серверу', 'status': 'ok' if db_connection_ok else 'todo'},
            {'title': 'DB constraints/audit/evidence доступны', 'status': 'ok' if db_schema_ready else 'todo', 'details': ', '.join(db_state.get('missing_tables') or [])},
        ],
        'blocks_next': not db_ok,
    })

    validate_state = 'ok' if validate_ok else ('locked' if not db_ok else 'todo')
    steps.append({
        'id': 'validate',
        'n': 2,
        'title': 'Проверка проекта и фиксация CI evidence',
        'goal': 'Одна кнопка запускает validate; после PASS панель сама предлагает записать CI PASS.',
        'status': validate_state,
        'operator_text': 'Никаких команд руками: запускайте проверку из этой карточки.',
        'action_id': None if validate_ok else ('run_validate' if db_ok else None),
        'primary_button': None if validate_ok else 'Запустить validate',
        'substeps': [
            {'title': 'compileall/pytest/static checks/secret scan', 'status': 'ok' if validate_ok else validate_state},
            {'title': 'CI evidence PASS записан в БД', 'status': 'ok' if ci_ok else ('todo' if validate_ok and db_ok else validate_state), 'action_id': None if ci_ok else ('record_ci_pass' if validate_ok and db_ok else None), 'button': None if ci_ok else ('Записать CI PASS' if validate_ok and db_ok else None)},
        ],
        'blocks_next': not validate_ok or not ci_ok,
    })

    testnet_state = 'ok' if testnet_ok else ('locked' if not (validate_ok and ci_ok) else 'todo')
    steps.append({
        'id': 'testnet_preflight',
        'n': 3,
        'title': 'Testnet preflight',
        'goal': 'Проверить Bybit testnet, runtime specs, permissions, wallet и positions из панели.',
        'status': testnet_state,
        'operator_text': 'PASS здесь означает, что testnet-контур подтвержден; live все равно закрыт.',
        'action_id': None if testnet_ok else ('run_testnet_preflight' if validate_ok and ci_ok else None),
        'primary_button': None if testnet_ok else 'Запустить testnet preflight',
        'substeps': [
            {'title': 'Bybit public/private API, permissions, wallet, positions', 'status': testnet_state},
            {'title': 'BTC/ETH/SOL runtime specs verified', 'status': testnet_state},
        ],
        'blocks_next': not testnet_ok,
    })

    paper_status = 'ok' if paper_pass else ('running' if paper_started else ('locked' if not testnet_ok else 'todo'))
    paper_sub = [
        {'title': 'PHASE0_PAPER evidence создан', 'status': 'ok' if paper_started else paper_status, 'action_id': None if paper_started else ('start_phase0_paper' if testnet_ok else None), 'button': None if paper_started else ('Начать 14-дневный paper/shadow' if testnet_ok else None)},
        {'title': f'Накоплено дней: {paper_days:.2f} из 14', 'status': 'ok' if paper_days >= 14 else ('running' if paper_started else paper_status)},
        {'title': 'Paper один раз без live-order', 'status': 'todo' if paper_started and not paper_pass else paper_status, 'action_id': 'run_paper_once' if paper_started and not paper_pass else None, 'button': 'Запустить paper один раз' if paper_started and not paper_pass else None},
        {'title': 'PHASE0_PAPER PASS после 14+ дней', 'status': 'ok' if paper_pass else ('todo' if paper_started and paper_days >= 14 else 'locked'), 'action_id': None if paper_pass else ('record_phase0_paper_pass' if paper_started and paper_days >= 14 else None), 'button': None if paper_pass else ('Записать PHASE0_PAPER PASS' if paper_started and paper_days >= 14 else None)},
    ]
    steps.append({
        'id': 'paper_shadow',
        'n': 4,
        'title': 'Phase 0 paper/shadow evidence',
        'goal': 'Не разовый клик, а контролируемое накопление evidence: старт, paper-прогоны, счетчик 14 дней, PASS.',
        'status': paper_status,
        'operator_text': 'Панель показывает, сколько дней накоплено. До 14 дней следующий gate закрыт.',
        'action_id': None if paper_started else ('start_phase0_paper' if testnet_ok else None),
        'primary_button': None if paper_started else 'Начать paper/shadow период',
        'substeps': paper_sub,
        'blocks_next': not paper_pass,
        'metrics': {'paper_days': paper_days, 'days_required': 14},
    })

    security_state = 'ok' if security_ok else ('locked' if not paper_pass else 'todo')
    steps.append({
        'id': 'security',
        'n': 5,
        'title': 'Security evidence',
        'goal': 'Зафиксировать, что secret scan и безопасные defaults пройдены.',
        'status': security_state,
        'operator_text': 'Кнопка доступна только после paper/shadow PASS.',
        'action_id': None if security_ok else ('record_security_pass' if paper_pass else None),
        'primary_button': None if security_ok else 'Записать SECURITY PASS',
        'substeps': [
            {'title': 'secret scan / frontend keys / dangerous defaults', 'status': security_state},
        ],
        'blocks_next': not security_ok,
    })

    rec_state = 'ok' if rec_ok else ('locked' if not security_ok else 'todo')
    steps.append({
        'id': 'reconciliation',
        'n': 6,
        'title': 'Reconciliation evidence',
        'goal': 'Подтвердить, что local/exchange state не расходятся и нет ACTIVE без protection.',
        'status': rec_state,
        'operator_text': 'Панель записывает PASS только как audited evidence; live-order от этого не включается.',
        'action_id': None if rec_ok else ('record_reconciliation_pass' if security_ok else None),
        'primary_button': None if rec_ok else 'Записать RECONCILIATION PASS',
        'substeps': [
            {'title': 'Нет unknown exchange position / нет unprotected ACTIVE', 'status': rec_state},
        ],
        'blocks_next': not rec_ok,
    })

    go_state = 'ok' if go_ok else ('locked' if not rec_ok else 'todo')
    steps.append({
        'id': 'go_no_go',
        'n': 7,
        'title': 'Подписанный Go/No-Go',
        'goal': 'Финальное решение владельца продукта. До него live невозможен.',
        'status': go_state,
        'operator_text': 'Нужен approved_by. Это не кнопка старта торговли.',
        'action_id': None if go_ok else ('record_go_no_go_pass' if rec_ok else None),
        'primary_button': None if go_ok else 'Записать GO/NO-GO PASS',
        'requires_approved_by': True,
        'substeps': [
            {'title': 'GO_NO_GO PASS с approved_by', 'status': go_state},
        ],
        'blocks_next': not go_ok,
    })

    live_state = live_preflight_state if go_ok else 'locked'
    steps.append({
        'id': 'live_preflight',
        'n': 8,
        'title': 'Live preflight',
        'goal': 'Последняя проверка live-gates. Даже PASS не отправляет ордера.',
        'status': live_state,
        'operator_text': 'Live-submit останется закрытым, пока env-флаги не подтверждены явно.',
        'action_id': 'run_live_preflight' if go_ok else None,
        'primary_button': 'Запустить live preflight' if go_ok else None,
        'substeps': [
            {'title': 'Go/No-Go evidence, live flags, unresolved CRITICAL/HIGH=0', 'status': live_state},
        ],
        'blocks_next': live_state != 'ok',
    })

    current = next((s for s in steps if s.get('status') not in {'ok'}), steps[-1])
    complete = all(step.get('status') == 'ok' for step in steps[:-1]) and steps[-1].get('status') == 'ok'
    blocked = [step for step in steps if step.get('status') in {'blocked', 'error'}]
    locked = [step for step in steps if step.get('status') == 'locked']

    return {
        'source_of_truth': 'backend_operator_workflow',
        'app': settings.app_name,
        'version': 'operator-workflow-v1',
        'mode': 'live_requested' if settings.live_requested else 'testnet_or_local_safe',
        'config_hash': runtime.config_hash,
        'hero': {
            'level': 'ok' if not blocked else 'danger',
            'title': 'Операторский мастер запуска',
            'message': 'Все ключевые вехи упакованы во frontend: шаги идут строго сверху вниз, следующий gate закрыт до завершения подшагов.',
            'next_step': f"Шаг {current['n']}: {current['title']}",
        },
        'current_step_id': current['id'],
        'complete': complete,
        'steps': steps,
        'blocked_count': len(blocked),
        'locked_count': len(locked),
        'evidence': evidence,
        'jobs': getattr(request.app.state, 'operator_jobs').list_jobs(limit=10),
        'invariants': [
            'Нет approved non-expired risk_decision_id -> нет order',
            'Нет verified protection -> нет ACTIVE',
            'Frontend не источник истины: он отображает backend workflow/status_effective',
            'Live невозможен до Go/No-Go PASS и unresolved CRITICAL/HIGH = 0',
        ],
        'repository_available': repo is not None,
        'database_available': db_connection_ok,
        'database_schema_ready': db_schema_ready,
        'database_missing_tables': db_state.get('missing_tables') or [],
        'database_error': db_state.get('error'),
    }


def _record_evidence(request: Request, evidence_type: str, status: str, actor: str, approved_by: str | None, metrics: dict[str, Any] | None = None, started_at: str | None = None, ended_at: str | None = None) -> None:
    repo = getattr(request.app.state, 'repository', None)
    if repo is None:
        raise HTTPException(status_code=409, detail='database_required_for_evidence')
    if evidence_type == 'GO_NO_GO' and status == 'PASS' and not approved_by:
        raise HTTPException(status_code=400, detail='approved_by_required_for_go_no_go_pass')
    repo.record_go_no_go_evidence(
        evidence_type=evidence_type,
        status=status,
        config_hash=request.app.state.runtime_config.config_hash,
        trace_id=new_trace_id('wf'),
        metrics=metrics or {'actor': actor, 'recorded_from': 'operator_workflow_ui'},
        started_at=started_at,
        ended_at=ended_at,
        approved_by=approved_by or actor,
    )


@router.get('')
async def get_workflow(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    return ApiEnvelope(request_id=rid, status='ok', data=build_workflow(request))


@router.post('/actions/{action_id}')
async def run_workflow_action(
    action_id: str,
    request: Request,
    body: WorkflowActionRequest,
    rid: str = Depends(request_id),
    actor: str = Depends(require_operator),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
) -> ApiEnvelope:
    if not x_idempotency_key:
        raise HTTPException(status_code=400, detail='idempotency_key_required')
    idem_key = namespaced_idempotency_key('operator-workflow', f'{action_id}:{x_idempotency_key}')
    cached = request.app.state.idempotency.get(idem_key)
    if cached:
        return ApiEnvelope(request_id=rid, trace_id=cached['trace_id'], status=cached['status'], reasons=cached['reasons'], data=cached['data'])

    workflow = build_workflow(request)
    step_by_action = {step.get('action_id'): step for step in workflow['steps'] if step.get('action_id')}
    for step in workflow['steps']:
        for sub in step.get('substeps', []):
            if sub.get('action_id'):
                step_by_action[sub['action_id']] = step
    step = step_by_action.get(action_id)
    if step is None and action_id not in {'run_paper_once'}:
        raise HTTPException(status_code=404, detail='workflow_action_not_available_or_locked')
    if step is not None and step.get('status') == 'locked':
        raise HTTPException(status_code=409, detail='previous_workflow_steps_are_not_completed')

    data: dict[str, Any]
    status = 'ok'
    reasons: list[str] = []
    trace_id = new_trace_id('wf')

    command_map = {
        'run_bootstrap_db': 'bootstrap_db',
        'run_validate': 'validate',
        'run_testnet_preflight': 'preflight_testnet',
        'run_live_preflight': 'preflight_live',
    }
    if action_id in command_map:
        job = request.app.state.operator_jobs.start(
            command_id=command_map[action_id],
            actor=actor,
            reason=body.reason,
            options=body.options,
        )
        status = 'accepted'
        data = {'job': job, 'refresh_after_job': True}
    elif action_id == 'record_ci_pass':
        _record_evidence(request, 'CI', 'PASS', actor, body.approved_by, {'source': 'operator_workflow', 'validated_by_operator': True})
        data = {'evidence_type': 'CI', 'status': 'PASS'}
    elif action_id == 'start_phase0_paper':
        _record_evidence(request, 'PHASE0_PAPER', 'PENDING', actor, body.approved_by, {'source': 'operator_workflow', 'days_required': 14, 'days_completed': 0}, started_at=_iso_now())
        data = {'evidence_type': 'PHASE0_PAPER', 'status': 'PENDING'}
    elif action_id == 'run_paper_once':
        pipeline = PaperPipeline(request.app.state.demo_state, allow_demo_ml=request.app.state.settings.allow_demo_ml, runtime_config=request.app.state.runtime_config)
        data = {'paper': pipeline.run_once()}
    elif action_id == 'record_phase0_paper_pass':
        paper = _evidence_rows(request).get('PHASE0_PAPER')
        days = _paper_days(paper)
        if days < 14:
            raise HTTPException(status_code=409, detail='phase0_paper_min_14_days_required')
        started_at = paper.get('started_at') if paper else None
        _record_evidence(request, 'PHASE0_PAPER', 'PASS', actor, body.approved_by, {'source': 'operator_workflow', 'days_completed': days}, started_at=started_at, ended_at=_iso_now())
        data = {'evidence_type': 'PHASE0_PAPER', 'status': 'PASS', 'paper_days': days}
    elif action_id == 'record_security_pass':
        _record_evidence(request, 'SECURITY', 'PASS', actor, body.approved_by, {'source': 'operator_workflow', 'secret_scan': 'PASS', 'frontend_keys': 'absent'})
        data = {'evidence_type': 'SECURITY', 'status': 'PASS'}
    elif action_id == 'record_reconciliation_pass':
        _record_evidence(request, 'RECONCILIATION', 'PASS', actor, body.approved_by, {'source': 'operator_workflow', 'active_without_protection': 0, 'unknown_exchange_position': 0})
        data = {'evidence_type': 'RECONCILIATION', 'status': 'PASS'}
    elif action_id == 'record_go_no_go_pass':
        wf = build_workflow(request)
        prerequisites = {s['id']: s['status'] for s in wf['steps']}
        for req_id in ['db', 'validate', 'testnet_preflight', 'paper_shadow', 'security', 'reconciliation']:
            if prerequisites.get(req_id) != 'ok':
                raise HTTPException(status_code=409, detail=f'go_no_go_blocked_until_{req_id}_ok')
        _record_evidence(request, 'GO_NO_GO', 'PASS', actor, body.approved_by, {'source': 'operator_workflow', 'signed_by': body.approved_by or actor})
        data = {'evidence_type': 'GO_NO_GO', 'status': 'PASS'}
    else:
        raise HTTPException(status_code=404, detail='workflow_action_not_found')

    payload = {'trace_id': trace_id, 'status': status, 'reasons': reasons, 'data': data}
    request.app.state.idempotency.put(idem_key, payload)
    return ApiEnvelope(request_id=rid, trace_id=trace_id, status=status, reasons=reasons, data=data)

from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read
from app.live.preflight import run_live_preflight
from app.db.availability import ensure_database_ready

router = APIRouter(prefix='/api/runtime', tags=['runtime'])


@router.get('/preflight')
async def preflight(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    """Runtime gate: local smoke в demo и строгий live-preflight при live-флагах."""

    ensure_database_ready(request.app)
    settings = request.app.state.settings
    runtime = request.app.state.runtime_config
    state = request.app.state.demo_state

    if settings.live_requested:
        result = run_live_preflight(
            settings=settings,
            runtime=runtime,
            db_available=bool(getattr(request.app.state, 'db_available', False)) and bool(getattr(request.app.state, 'db_schema_ready', False)),
            repository=getattr(request.app.state, 'repository', None),
        )
        return ApiEnvelope(request_id=rid, status=result.status, reasons=result.reasons, data={
            **result.data,
            'checks': result.checks,
            'live_order_submit_enabled': result.ok and settings.can_live_trade,
            'operator_writes_require_key': True,
            'frontend_source_of_truth': 'backend_status_effective',
            'database_available': bool(getattr(request.app.state, 'db_available', False)),
            'database_schema_ready': bool(getattr(request.app.state, 'db_schema_ready', False)),
            'db_startup_error': getattr(request.app.state, 'db_startup_error', None),
        })

    # Local/demo smoke: без внешних Bybit-вызовов, но с TTL/status проверками.
    reasons: list[str] = []
    for symbol in runtime.live_universe:
        specs = state.specs.get(symbol)
        market = state.market.get(symbol)
        if specs is None or not specs.fresh:
            reasons.append(f'{symbol}:stale_or_missing_specs')
        if market is None or not market.fresh:
            reasons.append(f'{symbol}:stale_or_missing_market')
    status = 'ok' if not reasons else 'blocked'
    return ApiEnvelope(request_id=rid, status=status, reasons=reasons, data={
        'config_hash': runtime.config_hash,
        'phase': runtime.phase,
        'exchange_scope': 'bybit_v5_linear_usdt_only',
        'live_order_submit_enabled': False,
        'operator_writes_require_key': True,
        'frontend_source_of_truth': 'backend_status_effective',
        'database_available': bool(getattr(request.app.state, 'db_available', False)),
        'database_schema_ready': bool(getattr(request.app.state, 'db_schema_ready', False)),
        'db_startup_error': getattr(request.app.state, 'db_startup_error', None),
        'mode': 'local_smoke',
    })

from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope

router = APIRouter(prefix='/api/health', tags=['health'])


@router.get('')
async def health(request: Request, rid: str = Depends(request_id)) -> ApiEnvelope:
    settings = request.app.state.settings
    return ApiEnvelope(request_id=rid, status='ok', data={
        'app': settings.app_name,
        'env': settings.app_env,
        'trading_enabled': settings.trading_enabled,
        'can_live_trade': settings.can_live_trade,
        'live_submit_explicitly_enabled': settings.enable_live_submit,
        'database_available': bool(getattr(request.app.state, 'db_available', False)),
        'exchange_scope': 'bybit_v5_linear_usdt_only',
        'frontend_framework': 'none',
        'config_hash': request.app.state.runtime_config.config_hash,
        'phase': request.app.state.runtime_config.phase,
    })

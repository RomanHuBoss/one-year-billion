from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read

router = APIRouter(prefix='/api/ml', tags=['ml'])


@router.get('/health')
async def ml_health(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    return ApiEnvelope(request_id=rid, status='ok', data={
        'role': 'ALLOW_BLOCK_UNAVAILABLE_gate_only',
        'missing_model_behavior': 'BLOCK_for_ml_required_strategy',
        'can_open_trade': False,
        'can_size_position': False,
        'demo_override': request.app.state.settings.allow_demo_ml,
    })

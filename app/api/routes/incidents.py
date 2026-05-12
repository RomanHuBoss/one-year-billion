from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read

router = APIRouter(prefix='/api/incidents', tags=['incidents'])


@router.get('')
async def incidents(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    repo = getattr(request.app.state, 'repository', None)
    if repo is not None:
        return ApiEnvelope(request_id=rid, status='ok', data={'incidents': repo.open_incidents(), 'storage': 'postgresql'})
    return ApiEnvelope(request_id=rid, status='ok', data={'incidents': request.app.state.demo_state.incidents, 'storage': 'demo_state'})

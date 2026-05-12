from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read

router = APIRouter(prefix='/api/state', tags=['state'])


@router.get('/overview')
async def overview(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    repo = getattr(request.app.state, 'repository', None)
    if repo is not None:
        return ApiEnvelope(request_id=rid, status='ok', data={'symbols': repo.latest_statuses(), 'source_of_truth': 'backend_status_effective', 'storage': 'postgresql'})
    state = request.app.state.demo_state
    return ApiEnvelope(request_id=rid, status='ok', data={'symbols': state.overview(), 'source_of_truth': 'backend_status_effective', 'storage': 'demo_state'})

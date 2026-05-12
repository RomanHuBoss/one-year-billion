from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read
from app.paper_trading.pipeline import PaperPipeline

router = APIRouter(prefix='/api/paper', tags=['paper'])


@router.post('/run-once')
async def run_once(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    pipeline = PaperPipeline(request.app.state.demo_state, allow_demo_ml=request.app.state.settings.allow_demo_ml, runtime_config=request.app.state.runtime_config)
    return ApiEnvelope(request_id=rid, status='ok', data=pipeline.run_once())

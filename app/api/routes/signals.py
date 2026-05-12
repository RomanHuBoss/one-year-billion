from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read
from app.regime.classifier import RegimeClassifier
from app.strategies.orchestrator import StrategyOrchestrator
from app.config.phase_validator import validate_symbol_for_phase

router = APIRouter(prefix='/api/signals', tags=['signals'])


@router.get('/propose')
async def propose(request: Request, symbol: str = 'BTCUSDT', rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    state = request.app.state.demo_state
    runtime = request.app.state.runtime_config
    symbol = symbol.upper()
    symbol_check = validate_symbol_for_phase(symbol, runtime.phase, runtime.live_universe)
    if not symbol_check.allowed:
        return ApiEnvelope(request_id=rid, status='blocked', reasons=symbol_check.reasons, data={'candidates': []})
    if symbol not in state.market or symbol not in state.specs:
        return ApiEnvelope(request_id=rid, status='blocked', reasons=['symbol_runtime_data_missing'], data={'candidates': []})
    reg = RegimeClassifier().classify(state.market[symbol], state.account)
    candidates = StrategyOrchestrator().propose(state.market[symbol], state.account, reg)
    return ApiEnvelope(request_id=rid, trace_id=reg.trace_id, status='ok', data={'regime': reg.model_dump(mode='json'), 'candidates': [c.model_dump(mode='json') for c in candidates]})

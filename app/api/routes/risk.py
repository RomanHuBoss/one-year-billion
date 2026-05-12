from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.schemas.domain import SignalCandidate
from app.security.auth import require_read
from app.ml.inference import MLGate
from app.risk_engine.approval import approve_signal
from app.config.phase_validator import validate_symbol_for_phase, validate_strategy_for_phase
from app.execution.bybit_adapter import BybitAdapter, BybitConfig
from app.market_data.bybit_ingestion import BybitMarketDataIngestion

router = APIRouter(prefix='/api/risk', tags=['risk'])


@router.get('/status')
async def risk_status(request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    runtime = request.app.state.runtime_config
    return ApiEnvelope(request_id=rid, status='ok', data={
        'risk_engine': 'hard_gate',
        'order_requires_approved_non_expired_risk_decision': True,
        'target_equity_used_in_sizing': False,
        'risk_unavailable_behavior': 'fail_closed',
        'config_hash': runtime.config_hash,
        'phase': runtime.phase,
        'live_universe': runtime.live_universe,
        'live_strategies': runtime.live_strategies,
    })


@router.post('/approve')
async def approve(candidate: SignalCandidate, request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    state = request.app.state.demo_state
    runtime = request.app.state.runtime_config
    symbol_check = validate_symbol_for_phase(candidate.symbol, runtime.phase, runtime.live_universe)
    strategy_check = validate_strategy_for_phase(candidate.strategy, runtime.phase, runtime.live_strategies, runtime.shadow_strategies)
    gate_reasons = [*symbol_check.reasons, *strategy_check.reasons]
    if gate_reasons:
        return ApiEnvelope(request_id=rid, trace_id=candidate.trace_id, status='blocked', reasons=gate_reasons, data=None)
    repo = getattr(request.app.state, 'repository', None)
    settings = request.app.state.settings

    if settings.live_requested:
        if repo is None:
            return ApiEnvelope(request_id=rid, trace_id=candidate.trace_id, status='blocked', reasons=['database_required_for_live_risk_approval'], data=None)
        try:
            adapter = BybitAdapter(BybitConfig(settings.bybit_api_key, settings.bybit_api_secret, settings.bybit_testnet, settings.trading_enabled, settings.bybit_live_confirm))
            ingestion = BybitMarketDataIngestion(adapter)
            specs = ingestion.fetch_runtime_specs(candidate.symbol)
            market = ingestion.fetch_market_snapshot(candidate.symbol)
            account = ingestion.fetch_account_snapshot(phase=runtime.phase)
            repo.persist_instrument_spec(specs)
            repo.persist_market_snapshot(market)
            repo.persist_account_snapshot(account)
        except Exception as exc:
            if repo is not None:
                repo.persist_signal(candidate, status='BLOCKED', reasons=[f'live_runtime_data_unavailable:{type(exc).__name__}'])
                repo.create_incident('HIGH', 'LIVE_RUNTIME_DATA_UNAVAILABLE', 'risk', candidate.symbol, {'error': f'{type(exc).__name__}:{exc}'}, candidate.trace_id)
            return ApiEnvelope(request_id=rid, trace_id=candidate.trace_id, status='blocked', reasons=[f'live_runtime_data_unavailable:{type(exc).__name__}'], data=None)
    else:
        if candidate.symbol not in state.specs or candidate.symbol not in state.market:
            return ApiEnvelope(request_id=rid, trace_id=candidate.trace_id, status='blocked', reasons=['symbol_runtime_data_missing'], data=None)
        specs = state.specs[candidate.symbol]
        market = state.market[candidate.symbol]
        account = state.account

    ml = MLGate(allow_demo_ml=settings.allow_demo_ml).evaluate(candidate)
    risk = approve_signal(candidate, ml, account, market, specs, runtime.risk, runtime.costs)
    if repo is not None:
        repo.persist_signal(candidate, status='APPROVED' if risk.approved else 'RISK_REJECTED', reasons=risk.reasons)
        repo.persist_ml_prediction(candidate.signal_id, ml)
        repo.persist_risk_decision(risk)
    return ApiEnvelope(request_id=rid, trace_id=candidate.trace_id, status='ok' if risk.approved else 'rejected', reasons=risk.reasons, data={'ml': ml.model_dump(), 'risk_decision': risk.model_dump(mode='json'), 'persisted': repo is not None, 'runtime_source': 'bybit_live' if settings.live_requested else 'demo_state'})

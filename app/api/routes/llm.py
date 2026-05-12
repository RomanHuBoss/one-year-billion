from __future__ import annotations
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request
from app.api.dependencies import request_id
from app.schemas.api_contract import ApiEnvelope
from app.security.auth import require_read
from app.llm.ollama_client import OllamaClient
from app.llm.news_risk import NewsRiskGate

router = APIRouter(prefix='/api/llm', tags=['llm'])


class NewsText(BaseModel):
    text: str
    symbol: str | None = None


@router.post('/news-risk')
async def news_risk(req: NewsText, request: Request, rid: str = Depends(request_id), actor: str = Depends(require_read)) -> ApiEnvelope:
    s = request.app.state.settings
    gate = NewsRiskGate(OllamaClient(s.ollama_base_url, s.ollama_model))
    result = gate.evaluate_text(req.text, req.symbol)
    return ApiEnvelope(request_id=rid, status='ok' if result['verdict'] != 'UNAVAILABLE' else 'degraded', reasons=[result['reason']], data=result)

from __future__ import annotations
from app.llm.ollama_client import OllamaClient

ALLOWED = {'BLOCK','ANNOTATE','UNAVAILABLE'}


class NewsRiskGate:
    def __init__(self, client: OllamaClient):
        self.client = client

    def evaluate_text(self, text: str, symbol: str | None = None) -> dict:
        prompt = f"""
You are a risk annotation layer for a Bybit linear USDT futures system.
You may ONLY return JSON with verdict BLOCK, ANNOTATE, or UNAVAILABLE.
Never recommend opening a trade, increasing size, changing leverage, or overriding risk.
Symbol: {symbol or 'GLOBAL'}
Text: {text[:4000]}
Return keys: verdict, severity, reason.
"""
        result = self.client.generate_json(prompt)
        verdict = str(result.get('verdict', 'UNAVAILABLE')).upper()
        if verdict not in ALLOWED:
            verdict = 'UNAVAILABLE'
        return {'verdict': verdict, 'severity': result.get('severity','medium'), 'reason': result.get('reason','llm_no_reason')}

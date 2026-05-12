from __future__ import annotations
import json
from dataclasses import dataclass
import httpx


@dataclass(frozen=True)
class OllamaClient:
    base_url: str = 'http://127.0.0.1:11434'
    model: str = 'llama3.1'

    def generate_json(self, prompt: str) -> dict:
        payload = {'model': self.model, 'prompt': prompt, 'stream': False, 'format': 'json'}
        try:
            with httpx.Client(timeout=20) as client:
                r = client.post(f'{self.base_url}/api/generate', json=payload)
                r.raise_for_status()
                response = r.json().get('response', '{}')
                return json.loads(response)
        except Exception as exc:
            return {'verdict': 'UNAVAILABLE', 'reason': f'ollama_unavailable:{type(exc).__name__}'}

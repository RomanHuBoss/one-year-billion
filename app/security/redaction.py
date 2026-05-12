from __future__ import annotations
from typing import Any

SECRET_KEYS = {'api_key','apiSecret','api_secret','secret','token','password','authorization'}


def redact(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: ('***REDACTED***' if k.lower() in SECRET_KEYS else redact(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [redact(x) for x in data]
    return data

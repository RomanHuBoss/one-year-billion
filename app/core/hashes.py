from __future__ import annotations
import hashlib, json, uuid
from typing import Any


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def hash_payload(data: Any) -> str:
    return sha256_text(stable_json(data))


def new_trace_id(prefix: str = 'trace') -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

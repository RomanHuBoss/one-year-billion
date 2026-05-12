from __future__ import annotations
from fastapi import Request
from app.core.hashes import new_trace_id


def request_id(request: Request) -> str:
    rid = request.headers.get('x-request-id')
    return rid or new_trace_id('req')

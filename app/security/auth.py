from __future__ import annotations
from fastapi import Header, HTTPException, Request


async def require_read(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    settings = request.app.state.settings
    if x_api_key in {settings.operator_api_key, settings.readonly_api_key}:
        return 'reader' if x_api_key == settings.readonly_api_key else 'operator'
    # Local dashboard reads are allowed in demo/local only; writes still require operator key.
    if settings.app_env == 'local':
        return 'local_reader'
    raise HTTPException(status_code=401, detail='invalid_api_key')


async def require_operator(request: Request, x_api_key: str | None = Header(default=None)) -> str:
    settings = request.app.state.settings
    if x_api_key == settings.operator_api_key:
        return 'operator'
    raise HTTPException(status_code=403, detail='operator_key_required')

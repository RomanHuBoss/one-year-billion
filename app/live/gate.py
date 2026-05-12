from __future__ import annotations
from fastapi import HTTPException, Request
from app.live.preflight import run_live_preflight


def assert_live_submit_allowed(request: Request) -> dict:
    """Единая точка запрета live-submit.

    Здесь намеренно нет bypass-параметров: если хоть один gate не пройден,
    route возвращает 423 Locked и не доходит до BybitAdapter.place_order().
    """

    settings = request.app.state.settings
    runtime = request.app.state.runtime_config
    result = run_live_preflight(
        settings=settings,
        runtime=runtime,
        db_available=bool(getattr(request.app.state, 'db_available', False)),
        repository=getattr(request.app.state, 'repository', None),
    )
    if not result.ok:
        raise HTTPException(status_code=423, detail={'live_submit_blocked': result.reasons, 'checks': result.checks})
    return {'checks': result.checks, 'data': result.data}

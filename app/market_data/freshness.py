from __future__ import annotations
from datetime import datetime
from app.core.time import utc_now


def is_fresh(expires_at: datetime | None) -> bool:
    return bool(expires_at and expires_at > utc_now())


def freshness_reason(name: str, expires_at: datetime | None) -> str | None:
    if not is_fresh(expires_at):
        return f'stale_{name}'
    return None

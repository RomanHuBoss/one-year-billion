from __future__ import annotations
from datetime import datetime, timezone, timedelta


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seconds_from_now(seconds: int) -> datetime:
    return utc_now() + timedelta(seconds=seconds)

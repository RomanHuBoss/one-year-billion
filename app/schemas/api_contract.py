from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.core.time import utc_now


class ApiEnvelope(BaseModel):
    request_id: str
    trace_id: str | None = None
    server_time: datetime = Field(default_factory=utc_now)
    status: str = 'ok'
    reasons: list[str] = Field(default_factory=list)
    data: Any = None


class StatusView(BaseModel):
    symbol: str
    status_effective: str
    severity: str
    reasons: list[str]
    trace_id: str
    allowed_actions: list[str]
    updated_at: datetime


class ActionRequest(BaseModel):
    action: str
    reason: str
    target: dict[str, Any] = Field(default_factory=dict)


class ManualActionResult(BaseModel):
    accepted: bool
    action: str
    reduce_only: bool = True
    reasons: list[str]
    trace_id: str

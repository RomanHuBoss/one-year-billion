from __future__ import annotations
from app.schemas.domain import OrderState

ALLOWED = {
    OrderState.PENDING_SIGNAL: {OrderState.APPROVED, OrderState.RISK_REJECTED, OrderState.BLOCKED},
    OrderState.RISK_REJECTED: {OrderState.CLOSED},
    OrderState.APPROVED: {OrderState.ORDER_SUBMITTED, OrderState.BLOCKED},
    OrderState.ORDER_SUBMITTED: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CLOSED, OrderState.ERROR_RECONCILIATION_REQUIRED},
    OrderState.PARTIALLY_FILLED: {OrderState.FILLED, OrderState.REDUCE_ONLY_EXITING, OrderState.ERROR_RECONCILIATION_REQUIRED},
    OrderState.FILLED: {OrderState.PROTECTED_WITH_SLTP, OrderState.REDUCE_ONLY_EXITING, OrderState.ERROR_RECONCILIATION_REQUIRED},
    OrderState.PROTECTED_WITH_SLTP: {OrderState.REDUCE_ONLY_EXITING, OrderState.CLOSED, OrderState.ERROR_RECONCILIATION_REQUIRED},
    OrderState.REDUCE_ONLY_EXITING: {OrderState.CLOSED, OrderState.ERROR_RECONCILIATION_REQUIRED},
    OrderState.CLOSED: {OrderState.PENDING_SIGNAL},
    OrderState.ERROR_RECONCILIATION_REQUIRED: {OrderState.REDUCE_ONLY_EXITING, OrderState.CLOSED, OrderState.BLOCKED},
    OrderState.BLOCKED: {OrderState.PENDING_SIGNAL},
    OrderState.DE_RISK: {OrderState.REDUCE_ONLY_EXITING, OrderState.CLOSED, OrderState.BLOCKED},
}


def can_transition(src: OrderState, dst: OrderState) -> bool:
    return dst in ALLOWED.get(src, set())


def assert_transition(src: OrderState, dst: OrderState) -> None:
    if not can_transition(src, dst):
        raise ValueError(f'forbidden_transition:{src}->{dst}')


def active_allowed(protection_state: str, reconciliation_status: str) -> bool:
    return protection_state == 'VALID' and reconciliation_status == 'PASS'

from app.execution.state_machine import active_allowed, can_transition
from app.schemas.domain import OrderState


def test_active_requires_protection():
    assert active_allowed('VALID','PASS') is True
    assert active_allowed('NONE','PASS') is False
    assert active_allowed('VALID','MISMATCH') is False


def test_no_submit_without_approval_transition():
    assert not can_transition(OrderState.PENDING_SIGNAL, OrderState.ORDER_SUBMITTED)
    assert can_transition(OrderState.APPROVED, OrderState.ORDER_SUBMITTED)

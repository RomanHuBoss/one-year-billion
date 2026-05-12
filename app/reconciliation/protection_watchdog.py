from __future__ import annotations
from app.schemas.domain import PositionState


def protection_valid(position: PositionState) -> bool:
    return bool(position.qty and position.sl_price and position.protection_state == 'VALID' and position.reconciliation_status == 'PASS')


def watchdog_action(position: PositionState) -> tuple[str, list[str]]:
    if position.state == 'ACTIVE' and not protection_valid(position):
        return 'REDUCE_ONLY_EXITING', ['missing_or_invalid_protection']
    return 'OK', []

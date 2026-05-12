from __future__ import annotations
from app.schemas.domain import PositionState


def reconcile_position(local: PositionState | None, exchange: PositionState | None) -> tuple[str, list[str]]:
    if local is None and exchange is None:
        return 'PASS', []
    if local is None and exchange is not None and exchange.qty != 0:
        return 'ERROR_RECONCILIATION_REQUIRED', ['unknown_exchange_position']
    if local is not None and exchange is None and local.qty != 0:
        return 'ERROR_RECONCILIATION_REQUIRED', ['missing_exchange_position']
    if local and exchange:
        if local.symbol != exchange.symbol or abs(local.qty - exchange.qty) > 1e-12:
            return 'ERROR_RECONCILIATION_REQUIRED', ['position_mismatch']
        if local.state == 'ACTIVE' and not (local.protection_state == 'VALID' and local.reconciliation_status == 'PASS'):
            return 'ERROR_RECONCILIATION_REQUIRED', ['active_without_verified_protection']
    return 'PASS', []

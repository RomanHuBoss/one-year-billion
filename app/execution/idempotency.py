from __future__ import annotations
from app.core.hashes import sha256_text


def namespaced_idempotency_key(namespace: str, key: str) -> str:
    """Разделяет idempotency-key разных write-контуров.

    Один и тот же пользовательский ключ может случайно попасть в manual action и
    order-router. Namespace не дает manual response быть прочитанным как OrderIntent.
    """

    if not namespace or not key:
        raise ValueError('idempotency_namespace_and_key_required')
    return f'{namespace}:{key}'


def deterministic_order_link_id(signal_id: str, risk_decision_id: str, action: str, sequence: int = 1) -> str:
    digest = sha256_text(f'{signal_id}:{risk_decision_id}:{action}:{sequence}')[:20]
    return f'cas26-{action[:3]}-{digest}'[:36]


class InMemoryIdempotencyStore:
    """Локальное хранилище idempotency и symbol-lock для одного процесса backend.

    Для production с несколькими воркерами эти же правила дублируются в PostgreSQL:
    unique idempotency_key и partial unique index на pending entry по symbol.
    """

    def __init__(self):
        self._responses: dict[str, object] = {}
        self._symbol_locks: dict[str, str] = {}

    def get(self, key: str):
        return self._responses.get(key)

    def put(self, key: str, value: object) -> object:
        if not key:
            raise ValueError('idempotency_key_required')
        self._responses[key] = value
        return value

    def lock_symbol(self, symbol: str, idempotency_key: str) -> None:
        """Ставит межзапросный лок на symbol до CLOSED/BLOCKED/ERROR обработки."""

        if not idempotency_key:
            raise ValueError('idempotency_key_required')
        symbol = symbol.upper()
        existing_key = self._symbol_locks.get(symbol)
        if existing_key and existing_key != idempotency_key:
            raise ValueError('symbol_locked_pending_execution')
        self._symbol_locks[symbol] = idempotency_key

    def release_symbol(self, symbol: str, idempotency_key: str | None = None) -> None:
        symbol = symbol.upper()
        current = self._symbol_locks.get(symbol)
        if current and (idempotency_key is None or idempotency_key == current):
            self._symbol_locks.pop(symbol, None)

    def locked_by(self, symbol: str) -> str | None:
        return self._symbol_locks.get(symbol.upper())

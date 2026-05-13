from __future__ import annotations
from uuid import uuid4
from app.schemas.domain import OrderIntent, OrderState, RiskDecision, SignalCandidate
from app.execution.idempotency import InMemoryIdempotencyStore, deterministic_order_link_id, namespaced_idempotency_key


FORBIDDEN_PRODUCT_STRATEGIES = {'martingale', 'dca', 'spot_grid', 'inverse_futures', 'options', 'copy_trading', 'signal_bot', 'portfolio_bot'}
SHADOW_ONLY_STRATEGIES_PHASE_0_1 = {'carry', 'carry_live', 'funding', 'funding_carry', 'pair_statarb', 'statarb', 'statarb_live', 'stat_arb'}


class OrderRouter:
    def __init__(self, idempotency: InMemoryIdempotencyStore | None = None):
        self.idempotency = idempotency or InMemoryIdempotencyStore()

    def _assert_cached_request_matches(self, cached: OrderIntent, signal: SignalCandidate, risk: RiskDecision) -> None:
        """Повтор idempotency key допустим только для того же signal/risk."""

        if cached.signal_id != signal.signal_id or cached.risk_decision_id != risk.risk_decision_id:
            raise ValueError('idempotency_key_reused_with_different_request')

    def build_intent(self, signal: SignalCandidate, risk: RiskDecision, idempotency_key: str) -> OrderIntent:
        if not idempotency_key:
            raise ValueError('idempotency_key_required')
        idem_key = namespaced_idempotency_key('order', idempotency_key)
        cached = self.idempotency.get(idem_key)
        if cached:
            if not isinstance(cached, OrderIntent):
                raise ValueError('idempotency_key_reserved_for_other_domain')
            self._assert_cached_request_matches(cached, signal, risk)
            return cached
        strategy_name = signal.strategy.lower()
        if strategy_name in FORBIDDEN_PRODUCT_STRATEGIES:
            raise ValueError('strategy_forbidden_product_scope')
        if signal.shadow_only or strategy_name in SHADOW_ONLY_STRATEGIES_PHASE_0_1:
            raise ValueError('shadow_signal_has_no_live_route')
        if not risk.approved:
            raise ValueError('risk_decision_not_approved')
        if risk.expired:
            raise ValueError('risk_decision_expired')
        if risk.signal_id != signal.signal_id:
            raise ValueError('risk_signal_mismatch')
        if risk.feature_hash != signal.feature_hash:
            raise ValueError('risk_feature_hash_mismatch')
        if not signal.stop_price or not signal.invalidator:
            raise ValueError('missing_stop_or_invalidator')
        if not signal.feature_hash:
            raise ValueError('missing_feature_hash')
        if not signal.regime_id or not signal.feature_id or not signal.required_data:
            raise ValueError('incomplete_signal_lineage')
        if not signal.evidence and not signal.shadow_only:
            raise ValueError('missing_strategy_evidence')
        if risk.sizing.qty <= 0 or risk.sizing.notional <= 0:
            raise ValueError('invalid_approved_sizing')
        if risk.sizing.risk_budget <= 0 or risk.sizing.max_loss_if_stop > risk.sizing.risk_budget:
            raise ValueError('approved_sizing_breaks_risk_budget')
        if risk.sizing.expected_net_edge_bps <= 0:
            raise ValueError('no_positive_net_edge')
        # Межзапросный lock предотвращает второй entry-path по тому же symbol.
        self.idempotency.lock_symbol(signal.symbol, idem_key)
        client_order_id = deterministic_order_link_id(signal.signal_id, risk.risk_decision_id, 'entry')
        intent = OrderIntent(
            order_id=str(uuid4()), signal_id=signal.signal_id, risk_decision_id=risk.risk_decision_id,
            # Входы по умолчанию PostOnly: если биржа отменила maker-only заявку,
            # это обрабатывается state machine/reconciliation, а не скрытым taker fill.
            client_order_id=client_order_id, symbol=signal.symbol, side=signal.side, order_type='PostOnly',
            qty=risk.sizing.qty, price=signal.entry_price, reduce_only=False, state=OrderState.APPROVED,
            idempotency_key=idempotency_key, trace_id=signal.trace_id,
        )
        self.idempotency.put(idem_key, intent)
        return intent

    def release_symbol(self, symbol: str, idempotency_key: str | None = None) -> None:
        """Снимает лок после CLOSED/BLOCKED/ERROR_RECONCILIATION_REQUIRED обработки."""

        scoped = namespaced_idempotency_key('order', idempotency_key) if idempotency_key else None
        self.idempotency.release_symbol(symbol, scoped)

    def bybit_payload(self, intent: OrderIntent) -> dict:
        payload = {
            'category': 'linear',
            'symbol': intent.symbol,
            'side': 'Buy' if intent.side.value == 'BUY' else 'Sell',
            'orderType': 'Limit' if intent.order_type in {'Limit','PostOnly'} else 'Market',
            'qty': str(intent.qty),
            'price': str(intent.price) if intent.price else None,
            'timeInForce': 'PostOnly' if intent.order_type == 'PostOnly' else 'GTC',
            'reduceOnly': intent.reduce_only,
            'closeOnTrigger': True if intent.reduce_only and intent.order_type == 'Market' else None,
            'orderLinkId': intent.client_order_id,
        }
        return {k: v for k, v in payload.items() if v is not None}

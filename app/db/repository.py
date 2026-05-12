from __future__ import annotations
from datetime import datetime
from typing import Any
import json
from app.db.connection import Database
from app.core.hashes import hash_payload
from app.schemas.domain import AccountSnapshot, InstrumentSpec, MarketSnapshot, MLVerdict, OrderIntent, RiskDecision, SignalCandidate


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


class Repository:
    """PostgreSQL repository for production lineage.

    Комментарии намеренно на русском: этот слой является safety-layer, а не
    пассивным логгером. Любой live-route обязан писать signal/risk/order сюда,
    чтобы DB constraints могли остановить обход risk engine.
    """

    def __init__(self, db: Database):
        self.db = db

    def latest_statuses(self) -> list[dict[str, Any]]:
        return self.db.fetch_all('SELECT * FROM latest_symbol_status ORDER BY symbol')

    def open_incidents(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM incidents WHERE status='OPEN' ORDER BY created_at DESC LIMIT 100")

    def persist_instrument_spec(self, specs: InstrumentSpec, raw_payload_hash: str | None = None) -> None:
        # Runtime specs сохраняются версионно: сделка без свежего instruments-info
        # не должна получить risk approval.
        self.db.execute(
            """
            INSERT INTO instruments(symbol, category, status, tick_size, qty_step, min_qty,
                min_notional, max_leverage, specs_version, raw_payload_hash, fetched_at, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [specs.symbol, specs.category, specs.status, specs.tick_size, specs.qty_step,
             specs.min_qty, specs.min_notional, specs.max_leverage, specs.specs_version,
             raw_payload_hash or specs.specs_version, specs.fetched_at, specs.expires_at],
        )

    def persist_market_snapshot(self, market: MarketSnapshot, raw_topn_hash: str | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO orderbook_snapshots(symbol, ts, bid1, ask1, spread_bps, depth_0_5pct,
                depth_1pct, imbalance, raw_topn_hash, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            [market.symbol, market.fetched_at, market.bid1, market.ask1, market.spread_bps,
             market.depth_usdt, market.depth_usdt, 0, raw_topn_hash or hash_payload(market.model_dump(mode='json')), market.expires_at],
        )

    def persist_account_snapshot(self, account: AccountSnapshot, raw_payload_hash: str | None = None) -> None:
        self.db.execute(
            """
            INSERT INTO account_snapshots(equity_usdt, available_balance_usdt, account_mode,
                position_mismatch, realized_negative_today_usdt, realized_negative_week_usdt,
                portfolio_abs_notional_usdt, beta_adjusted_exposure_usdt, permissions_json,
                raw_payload_hash, fetched_at, expires_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
            """,
            [account.equity_usdt, account.available_balance_usdt, account.account_mode,
             account.position_mismatch, account.realized_negative_today_usdt,
             account.realized_negative_week_usdt, account.portfolio_abs_notional_usdt,
             account.beta_adjusted_exposure_usdt, _json({'runtime_checked': True}),
             raw_payload_hash or hash_payload(account.model_dump(mode='json')), account.fetched_at, account.expires_at],
        )

    def unresolved_critical_high(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM incidents WHERE status='OPEN' AND severity IN ('CRITICAL','HIGH') ORDER BY created_at DESC")

    def live_evidence_status(self, min_paper_days: int, config_hash: str) -> tuple[bool, list[str], dict[str, Any]]:
        """Проверяет, что Go/No-Go не является только env-флагом.

        Live по спецификации требует paper/shadow evidence, reconciliation PASS
        и подписанный Go/No-Go. Поэтому БД должна содержать проверяемые записи,
        а не только CAS_GO_NOGO_PASS=true в окружении.
        """

        reasons: list[str] = []
        data: dict[str, Any] = {}
        paper = self.db.fetch_one(
            """
            SELECT *, EXTRACT(EPOCH FROM (ended_at - started_at))/86400.0 AS days
            FROM go_no_go_evidence
            WHERE evidence_type='PHASE0_PAPER' AND status='PASS'
              AND config_hash=%s AND started_at IS NOT NULL AND ended_at IS NOT NULL
            ORDER BY ended_at DESC
            LIMIT 1
            """,
            [config_hash],
        )
        paper_days = float(paper['days']) if paper and paper.get('days') is not None else 0.0
        data['paper_days'] = paper_days
        if paper_days < float(min_paper_days):
            reasons.append('phase0_paper_evidence_missing_or_too_short')

        for evidence_type, reason in [
            ('RECONCILIATION', 'reconciliation_pass_evidence_missing'),
            ('SECURITY', 'security_scan_evidence_missing'),
            ('CI', 'ci_pass_evidence_missing'),
            ('GO_NO_GO', 'signed_go_no_go_evidence_missing'),
        ]:
            row = self.db.fetch_one(
                """
                SELECT * FROM go_no_go_evidence
                WHERE evidence_type=%s AND status='PASS' AND config_hash=%s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [evidence_type, config_hash],
            )
            data[evidence_type.lower()] = bool(row)
            if row is None:
                reasons.append(reason)
        return not reasons, reasons, data

    def log_manual_action(self, actor: str, action: str, reason: str, target: dict[str, Any], status: str, trace_id: str) -> None:
        self.db.execute(
            """
            INSERT INTO manual_request_log(actor, action, reason, status, target, trace_id)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s)
            """,
            [actor, action, reason, status, _json(target), trace_id],
        )

    def record_go_no_go_evidence(
        self,
        evidence_type: str,
        status: str,
        config_hash: str,
        trace_id: str,
        metrics: dict[str, Any] | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
        approved_by: str | None = None,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO go_no_go_evidence(evidence_type, status, started_at, ended_at,
                metrics_json, config_hash, approved_by, trace_id)
            VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
            """,
            [evidence_type, status, started_at, ended_at, _json(metrics or {}), config_hash, approved_by, trace_id],
        )

    def persist_signal(self, signal: SignalCandidate, status: str = 'PENDING_SIGNAL', reasons: list[str] | None = None) -> None:
        # regime_id/feature_id пишутся только если заранее заведены отдельные записи.
        # Иначе FK нарушит сохранение candidate; lineage все равно сохраняется через
        # feature_hash/evidence/trace_id.
        self.db.execute(
            """
            INSERT INTO signals(
                signal_id, strategy, symbol, side, entry_price, stop_price, invalidator,
                expected_gross_edge_bps, expected_holding_time_sec, required_data,
                trace_id, strategy_version, feature_hash, evidence_json, status, reasons
            ) VALUES (%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s)
            ON CONFLICT (signal_id) DO UPDATE SET
                status=EXCLUDED.status,
                reasons=EXCLUDED.reasons
            """,
            [
                signal.signal_id, signal.strategy, signal.symbol, signal.side.value,
                signal.entry_price, signal.stop_price, signal.invalidator,
                signal.expected_gross_edge_bps, signal.expected_holding_time_sec,
                _json(signal.required_data), signal.trace_id, signal.strategy_version,
                signal.feature_hash, _json(signal.evidence), status, reasons or [],
            ],
        )

    def persist_ml_prediction(self, signal_id: str, ml: MLVerdict) -> None:
        self.db.execute(
            """
            INSERT INTO ml_predictions(
                signal_id, model_id, p_hit_2r, uncertainty, verdict, reasons,
                feature_schema_hash, model_version
            ) VALUES (%s::uuid,%s,%s,%s,%s,%s,%s,%s)
            """,
            [
                signal_id, ml.model_id, ml.p_hit_2r, ml.uncertainty,
                ml.verdict.value, [ml.reason] if ml.reason else [], ml.feature_schema_hash, ml.model_id,
            ],
        )

    def persist_risk_decision(self, risk: RiskDecision) -> None:
        self.db.execute(
            """
            INSERT INTO risk_decisions(
                risk_decision_id, signal_id, approved, reasons, sizing_json, limits_snapshot,
                account_snapshot, specs_version, feature_hash, config_hash, trace_id,
                created_at, expires_at
            ) VALUES (%s::uuid,%s::uuid,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (risk_decision_id) DO NOTHING
            """,
            [
                risk.risk_decision_id, risk.signal_id, risk.approved, risk.reasons,
                _json(risk.sizing.model_dump(mode='json')),
                _json(risk.limits_snapshot), _json(risk.account_snapshot), risk.specs_version,
                risk.feature_hash, risk.config_hash, risk.trace_id, risk.created_at, risk.expires_at,
            ],
        )

    def get_risk_decision(self, risk_decision_id: str) -> dict[str, Any] | None:
        return self.db.fetch_one('SELECT * FROM risk_decisions WHERE risk_decision_id=%s::uuid', [risk_decision_id])

    def verify_live_risk_decision(self, risk: RiskDecision) -> tuple[bool, list[str]]:
        row = self.get_risk_decision(risk.risk_decision_id)
        if row is None:
            return False, ['risk_decision_not_persisted']
        reasons: list[str] = []
        if not row['approved']:
            reasons.append('risk_decision_not_approved_in_db')
        expires_at = row['expires_at']
        if isinstance(expires_at, datetime) and expires_at <= datetime.now(tz=expires_at.tzinfo):
            reasons.append('risk_decision_expired_in_db')
        if str(row['signal_id']) != risk.signal_id:
            reasons.append('risk_decision_signal_mismatch_db')
        if row['feature_hash'] != risk.feature_hash:
            reasons.append('risk_decision_feature_hash_mismatch_db')
        if row['config_hash'] != risk.config_hash:
            reasons.append('risk_decision_config_hash_mismatch_db')
        return not reasons, reasons

    def get_order_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        return self.db.fetch_one('SELECT * FROM orders WHERE idempotency_key=%s', [idempotency_key])

    def reserve_order_intent(self, intent: OrderIntent, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
        """Атомарно резервирует live order intent в PostgreSQL.

        Возвращает inserted=False при повторе idempotency-key, чтобы route не
        отправлял второй запрос на биржу. Это закрывает multi-worker scenario,
        который нельзя надежно решить in-memory idempotency store.
        """

        existing = self.get_order_by_idempotency(intent.idempotency_key)
        if existing is not None:
            return False, existing
        row = self.db.execute_returning_one(
            """
            INSERT INTO orders(
                order_id, signal_id, risk_decision_id, client_order_id, exchange_order_id,
                symbol, side, order_type, qty, price, reduce_only, state,
                idempotency_key, raw_request_hash, raw_response_hash, trace_id
            ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING *
            """,
            [
                intent.order_id, intent.signal_id, intent.risk_decision_id, intent.client_order_id,
                None, intent.symbol, intent.side.value, intent.order_type, intent.qty, intent.price,
                intent.reduce_only, intent.state.value, intent.idempotency_key, hash_payload(payload),
                None, intent.trace_id,
            ],
        )
        if row is not None:
            return True, row
        return False, self.get_order_by_idempotency(intent.idempotency_key)

    def persist_order_intent(self, intent: OrderIntent, payload: dict[str, Any], exchange_ack: dict[str, Any] | None = None) -> None:
        inserted, _ = self.reserve_order_intent(intent, payload)
        if exchange_ack:
            self.update_order_submitted(intent.client_order_id, exchange_ack)

    def update_order_submitted(self, client_order_id: str, exchange_ack: dict[str, Any]) -> None:
        self.db.execute(
            """
            UPDATE orders
            SET state='ORDER_SUBMITTED', exchange_order_id=%s, raw_response_hash=%s, updated_at=now()
            WHERE client_order_id=%s
            """,
            [(exchange_ack.get('result') or {}).get('orderId'), hash_payload(exchange_ack), client_order_id],
        )

    def mark_order_error(self, client_order_id: str, reason: str) -> None:
        # При неопределенном результате REST submit запрещено освобождать symbol:
        # состояние должно уйти в reconciliation, иначе retry может увеличить exposure.
        self.db.execute(
            """
            UPDATE orders
            SET state='ERROR_RECONCILIATION_REQUIRED', raw_response_hash=%s, updated_at=now()
            WHERE client_order_id=%s
            """,
            [hash_payload({'error': reason}), client_order_id],
        )

    def create_incident(self, severity: str, type_: str, component: str, symbol: str | None, payload: dict[str, Any], trace_id: str) -> None:
        self.db.execute(
            """
            INSERT INTO incidents(severity,type,component,symbol,status,payload,payload_hash,trace_id)
            VALUES (%s,%s,%s,%s,'OPEN',%s::jsonb,%s,%s)
            """,
            [severity, type_, component, symbol, _json(payload), hash_payload(payload), trace_id],
        )

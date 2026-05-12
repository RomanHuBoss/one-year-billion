BEGIN;

-- Дополнительные hard-invariants для уже существующих БД.
-- 0001 содержит базовую схему; эта миграция добавляет защиту от скрытых
-- обходов risk/execution через прямые SQL insert/update.

ALTER TABLE risk_decisions
    DROP CONSTRAINT IF EXISTS risk_approved_sizing_values_sane;
ALTER TABLE risk_decisions
    ADD CONSTRAINT risk_approved_sizing_values_sane CHECK (
        approved = false OR (
            (sizing_json ? 'qty')
            AND (sizing_json ? 'notional')
            AND (sizing_json ? 'risk_budget')
            AND (sizing_json ? 'max_loss_if_stop')
            AND (sizing_json ? 'expected_net_edge_bps')
            AND ((sizing_json->>'qty')::numeric > 0)
            AND ((sizing_json->>'notional')::numeric > 0)
            AND ((sizing_json->>'risk_budget')::numeric > 0)
            AND ((sizing_json->>'max_loss_if_stop')::numeric <= (sizing_json->>'risk_budget')::numeric)
            AND ((sizing_json->>'expected_net_edge_bps')::numeric > 0)
        )
    );

ALTER TABLE signals
    DROP CONSTRAINT IF EXISTS signals_product_scope_guard;
ALTER TABLE signals
    ADD CONSTRAINT signals_product_scope_guard CHECK (
        lower(strategy) NOT IN ('martingale','dca','spot_grid','inverse_futures','options','copy_trading','signal_bot','portfolio_bot')
    );

ALTER TABLE signals
    DROP CONSTRAINT IF EXISTS signals_trade_candidate_requires_lineage;
ALTER TABLE signals
    ADD CONSTRAINT signals_trade_candidate_requires_lineage CHECK (
        status IN ('SHADOW_SIGNAL','REJECTED','RISK_REJECTED')
        OR (
            stop_price IS NOT NULL
            AND invalidator IS NOT NULL
            AND feature_hash IS NOT NULL
            AND length(feature_hash) > 0
            AND jsonb_typeof(evidence_json) = 'object'
            AND evidence_json <> '{}'::jsonb
        )
    );

ALTER TABLE positions
    DROP CONSTRAINT IF EXISTS active_position_nonflat_qty;
ALTER TABLE positions
    ADD CONSTRAINT active_position_nonflat_qty CHECK (
        state <> 'ACTIVE' OR (side IN ('LONG','SHORT') AND qty > 0)
    );

ALTER TABLE manual_request_log
    DROP CONSTRAINT IF EXISTS manual_config_change_reduce_only;
ALTER TABLE manual_request_log
    ADD CONSTRAINT manual_config_change_reduce_only CHECK (
        action NOT IN ('PROPOSE_CONFIG','ACTIVATE_CONFIG')
        OR (
            coalesce(lower(target->>'risk_change'), 'same') IN ('same','decrease','risk_decrease')
            AND coalesce(lower(target->>'risk_increase'), 'false') NOT IN ('true','1','yes','on')
        )
    );

CREATE OR REPLACE FUNCTION validate_order_risk_decision()
RETURNS TRIGGER AS $$
DECLARE
    rd RECORD;
    sg RECORD;
    approved_qty NUMERIC;
    approved_notional NUMERIC;
BEGIN
    SELECT * INTO rd FROM risk_decisions WHERE risk_decision_id = NEW.risk_decision_id;
    IF rd.risk_decision_id IS NULL THEN
        RAISE EXCEPTION 'risk_decision_id not found';
    END IF;
    IF rd.approved IS NOT TRUE THEN
        RAISE EXCEPTION 'risk_decision_id is not approved';
    END IF;
    IF rd.expires_at <= now() THEN
        RAISE EXCEPTION 'risk_decision_id is expired';
    END IF;
    IF rd.signal_id <> NEW.signal_id THEN
        RAISE EXCEPTION 'risk_decision signal mismatch';
    END IF;

    SELECT * INTO sg FROM signals WHERE signal_id = NEW.signal_id;
    IF sg.signal_id IS NULL THEN
        RAISE EXCEPTION 'signal not found';
    END IF;
    IF sg.status IN ('SHADOW_SIGNAL','REJECTED','RISK_REJECTED') THEN
        RAISE EXCEPTION 'signal has no live order route';
    END IF;
    IF sg.feature_hash <> rd.feature_hash THEN
        RAISE EXCEPTION 'risk_decision feature_hash mismatch';
    END IF;
    IF sg.stop_price IS NULL OR sg.invalidator IS NULL THEN
        RAISE EXCEPTION 'signal missing stop or invalidator';
    END IF;

    approved_qty := (rd.sizing_json->>'qty')::numeric;
    approved_notional := (rd.sizing_json->>'notional')::numeric;
    IF NEW.reduce_only IS FALSE THEN
        IF NEW.state NOT IN ('APPROVED','ORDER_SUBMITTED') THEN
            RAISE EXCEPTION 'new entry order must start from approved/submitted state';
        END IF;
        IF NEW.qty > approved_qty THEN
            RAISE EXCEPTION 'order qty exceeds approved risk sizing';
        END IF;
        IF NEW.price IS NOT NULL AND (NEW.qty * NEW.price) > (approved_notional * 1.000001) THEN
            RAISE EXCEPTION 'order notional exceeds approved risk sizing';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_order_risk_decision ON orders;
CREATE TRIGGER trg_validate_order_risk_decision
BEFORE INSERT OR UPDATE OF risk_decision_id, signal_id, qty, price, state, reduce_only ON orders
FOR EACH ROW EXECUTE FUNCTION validate_order_risk_decision();

COMMIT;

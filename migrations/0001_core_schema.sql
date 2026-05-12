BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
    CREATE TYPE order_state AS ENUM (
        'PENDING_SIGNAL','RISK_REJECTED','APPROVED','ORDER_SUBMITTED','PARTIALLY_FILLED','FILLED',
        'PROTECTED_WITH_SLTP','REDUCE_ONLY_EXITING','CLOSED','ERROR_RECONCILIATION_REQUIRED','BLOCKED','DE_RISK'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE status_effective AS ENUM ('PENDING','ACTIVE','BLOCKED','NO_TRADE','DE_RISK','ERROR_RECONCILIATION_REQUIRED','CLOSED','REJECTED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE ml_verdict AS ENUM ('ALLOW','BLOCK','UNAVAILABLE');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE incident_severity AS ENUM ('LOW','MEDIUM','HIGH','CRITICAL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS instruments (
    instrument_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'linear',
    status TEXT NOT NULL,
    tick_size NUMERIC(30,12) NOT NULL,
    qty_step NUMERIC(30,12) NOT NULL,
    min_qty NUMERIC(30,12) NOT NULL,
    min_notional NUMERIC(30,12) NOT NULL,
    max_leverage NUMERIC(10,4) NOT NULL,
    specs_version TEXT NOT NULL,
    raw_payload_hash TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT instruments_linear_only CHECK (category = 'linear'),
    CONSTRAINT instruments_positive_specs CHECK (tick_size > 0 AND qty_step > 0 AND min_qty >= 0 AND min_notional >= 0)
);
CREATE INDEX IF NOT EXISTS idx_instruments_symbol_expires ON instruments(symbol, expires_at DESC);

CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(30,12) NOT NULL,
    high NUMERIC(30,12) NOT NULL,
    low NUMERIC(30,12) NOT NULL,
    close NUMERIC(30,12) NOT NULL,
    volume NUMERIC(30,12) NOT NULL,
    source TEXT NOT NULL DEFAULT 'bybit',
    closed_bar BOOLEAN NOT NULL DEFAULT TRUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(symbol, timeframe, open_time),
    CONSTRAINT candles_closed_only CHECK (closed_bar = TRUE),
    CONSTRAINT candles_ohlc CHECK (high >= low AND high >= open AND high >= close AND low <= open AND low <= close)
);

CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    bid1 NUMERIC(30,12) NOT NULL,
    ask1 NUMERIC(30,12) NOT NULL,
    spread_bps NUMERIC(18,8) NOT NULL,
    depth_0_5pct NUMERIC(30,8) NOT NULL,
    depth_1pct NUMERIC(30,8) NOT NULL,
    imbalance NUMERIC(18,8) NOT NULL DEFAULT 0,
    raw_topn_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(symbol, ts),
    CONSTRAINT ob_valid CHECK (ask1 >= bid1 AND spread_bps >= 0)
);
CREATE INDEX IF NOT EXISTS idx_ob_symbol_expires ON orderbook_snapshots(symbol, expires_at DESC);

CREATE TABLE IF NOT EXISTS funding_rates (
    symbol TEXT NOT NULL,
    funding_ts TIMESTAMPTZ NOT NULL,
    predicted_rate NUMERIC(20,12),
    realized_rate NUMERIC(20,12),
    interval_min INTEGER NOT NULL,
    source_ts TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(symbol, funding_ts)
);

CREATE TABLE IF NOT EXISTS open_interest (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    oi NUMERIC(30,8) NOT NULL,
    oi_delta NUMERIC(30,8) NOT NULL DEFAULT 0,
    source_ts TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(symbol, ts),
    CONSTRAINT oi_nonnegative CHECK (oi >= 0)
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    account_snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equity_usdt NUMERIC(30,8) NOT NULL,
    available_balance_usdt NUMERIC(30,8) NOT NULL,
    account_mode TEXT NOT NULL,
    position_mismatch BOOLEAN NOT NULL DEFAULT FALSE,
    realized_negative_today_usdt NUMERIC(30,8) NOT NULL DEFAULT 0,
    realized_negative_week_usdt NUMERIC(30,8) NOT NULL DEFAULT 0,
    portfolio_abs_notional_usdt NUMERIC(30,8) NOT NULL DEFAULT 0,
    beta_adjusted_exposure_usdt NUMERIC(30,8) NOT NULL DEFAULT 0,
    permissions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_payload_hash TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT equity_positive CHECK (equity_usdt >= 0 AND available_balance_usdt >= 0),
    CONSTRAINT account_risk_snapshots_nonnegative CHECK (
        realized_negative_today_usdt >= 0
        AND realized_negative_week_usdt >= 0
        AND portfolio_abs_notional_usdt >= 0
        AND beta_adjusted_exposure_usdt >= 0
    )
);
CREATE INDEX IF NOT EXISTS idx_account_expires ON account_snapshots(expires_at DESC);

CREATE TABLE IF NOT EXISTS features (
    feature_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    feature_version TEXT NOT NULL,
    vector_json JSONB NOT NULL,
    vector_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_features_symbol_ts ON features(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS regimes (
    regime_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    regime TEXT NOT NULL,
    confidence NUMERIC(10,6) NOT NULL,
    reasons TEXT[] NOT NULL DEFAULT '{}',
    thresholds_snapshot JSONB NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_regimes_symbol_ts ON regimes(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS signals (
    signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    entry_price NUMERIC(30,12) NOT NULL,
    stop_price NUMERIC(30,12),
    invalidator TEXT,
    expected_gross_edge_bps NUMERIC(18,8) NOT NULL DEFAULT 0,
    expected_net_edge_bps NUMERIC(18,8),
    expected_holding_time_sec INTEGER NOT NULL DEFAULT 0,
    required_data JSONB NOT NULL DEFAULT '[]'::jsonb,
    regime_id UUID REFERENCES regimes(regime_id),
    feature_id UUID REFERENCES features(feature_id),
    trace_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    feature_hash TEXT NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'PENDING_SIGNAL',
    reasons TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT signal_stop_required_for_trade CHECK (status IN ('SHADOW_SIGNAL','REJECTED') OR stop_price IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_signals_status_symbol ON signals(status, symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS ml_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES signals(signal_id),
    model_id TEXT,
    p_hit_2r NUMERIC(10,8),
    uncertainty NUMERIC(10,8),
    verdict ml_verdict NOT NULL,
    reasons TEXT[] NOT NULL DEFAULT '{}',
    feature_schema_hash TEXT,
    model_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    risk_decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES signals(signal_id),
    approved BOOLEAN NOT NULL,
    reasons TEXT[] NOT NULL DEFAULT '{}',
    sizing_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    limits_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    account_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    specs_version TEXT NOT NULL,
    feature_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT risk_approved_requires_sizing CHECK ((approved = false) OR (sizing_json ? 'qty' AND sizing_json ? 'max_loss_if_stop'))
);
CREATE INDEX IF NOT EXISTS idx_risk_signal_approved ON risk_decisions(signal_id, approved, expires_at DESC);

CREATE TABLE IF NOT EXISTS orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL REFERENCES signals(signal_id),
    risk_decision_id UUID NOT NULL REFERENCES risk_decisions(risk_decision_id),
    client_order_id TEXT NOT NULL UNIQUE,
    exchange_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    order_type TEXT NOT NULL,
    qty NUMERIC(30,12) NOT NULL,
    price NUMERIC(30,12),
    reduce_only BOOLEAN NOT NULL DEFAULT FALSE,
    state order_state NOT NULL DEFAULT 'APPROVED',
    idempotency_key TEXT NOT NULL,
    raw_request_hash TEXT NOT NULL,
    raw_response_hash TEXT,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT client_order_len CHECK (length(client_order_id) <= 36),
    CONSTRAINT qty_positive CHECK (qty > 0)
);
CREATE INDEX IF NOT EXISTS idx_orders_state_symbol ON orders(state, symbol, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_idempotency_key ON orders(idempotency_key);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_entry_per_symbol
ON orders(symbol)
WHERE reduce_only = FALSE AND state IN ('APPROVED','ORDER_SUBMITTED','PARTIALLY_FILLED','FILLED','PROTECTED_WITH_SLTP');

CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fills (
    fill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange_fill_id TEXT NOT NULL UNIQUE,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    qty NUMERIC(30,12) NOT NULL,
    price NUMERIC(30,12) NOT NULL,
    fee NUMERIC(30,12) NOT NULL DEFAULT 0,
    liquidity TEXT NOT NULL CHECK (liquidity IN ('MAKER','TAKER','UNKNOWN')),
    ts TIMESTAMPTZ NOT NULL,
    raw_payload_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    position_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('LONG','SHORT','FLAT')),
    qty NUMERIC(30,12) NOT NULL,
    avg_price NUMERIC(30,12),
    liq_price NUMERIC(30,12),
    sl_price NUMERIC(30,12),
    tp_price NUMERIC(30,12),
    state TEXT NOT NULL,
    protection_state TEXT NOT NULL DEFAULT 'NONE',
    reconciliation_status TEXT NOT NULL DEFAULT 'UNKNOWN',
    exchange_snapshot_hash TEXT,
    trace_id TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT active_position_protected CHECK (state <> 'ACTIVE' OR (protection_state = 'VALID' AND reconciliation_status = 'PASS'))
);
CREATE INDEX IF NOT EXISTS idx_positions_state_symbol ON positions(state, symbol);

CREATE TABLE IF NOT EXISTS trades_journal (
    trade_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES positions(position_id),
    realized_pnl NUMERIC(30,12) NOT NULL DEFAULT 0,
    realized_r NUMERIC(18,8),
    fees NUMERIC(30,12) NOT NULL DEFAULT 0,
    funding NUMERIC(30,12) NOT NULL DEFAULT 0,
    slippage NUMERIC(30,12) NOT NULL DEFAULT 0,
    mae NUMERIC(30,12),
    mfe NUMERIC(30,12),
    close_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    severity incident_severity NOT NULL,
    type TEXT NOT NULL,
    component TEXT NOT NULL,
    symbol TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload_hash TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_incidents_status_sev ON incidents(status, severity, created_at DESC);

CREATE TABLE IF NOT EXISTS system_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    trace_id TEXT,
    ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS configs (
    config_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_yaml TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT FALSE,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_config ON configs(active) WHERE active;

CREATE TABLE IF NOT EXISTS config_audit_log (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NOT NULL,
    reason TEXT NOT NULL,
    diff_json JSONB NOT NULL,
    approved_by TEXT,
    config_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS go_no_go_evidence (
    evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('PHASE0_PAPER','RECONCILIATION','SECURITY','CI','GO_NO_GO')),
    status TEXT NOT NULL CHECK (status IN ('PASS','FAIL','PENDING')),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    config_hash TEXT NOT NULL,
    approved_by TEXT,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT go_no_go_pass_requires_approver CHECK (evidence_type <> 'GO_NO_GO' OR status <> 'PASS' OR approved_by IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_go_no_go_evidence_type_status ON go_no_go_evidence(evidence_type, status, created_at DESC);

CREATE TABLE IF NOT EXISTS manual_request_log (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    target JSONB NOT NULL DEFAULT '{}'::jsonb,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT manual_reduce_only CHECK (action IN ('DISABLE_TRADING','CANCEL_OPEN_ENTRIES','FLATTEN_REDUCE','RESOLVE_INCIDENT','PROPOSE_CONFIG','ACTIVATE_CONFIG','REJECTED_UNSAFE_ACTION'))
);

CREATE OR REPLACE FUNCTION validate_order_risk_decision()
RETURNS TRIGGER AS $$
DECLARE rd RECORD;
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
    IF NEW.reduce_only IS FALSE AND NEW.state NOT IN ('APPROVED','ORDER_SUBMITTED') THEN
        RAISE EXCEPTION 'new entry order must start from approved/submitted state';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_order_risk_decision ON orders;
CREATE TRIGGER trg_validate_order_risk_decision
BEFORE INSERT OR UPDATE OF risk_decision_id, signal_id ON orders
FOR EACH ROW EXECUTE FUNCTION validate_order_risk_decision();

CREATE OR REPLACE VIEW latest_symbol_status AS
SELECT DISTINCT ON (s.symbol)
    s.symbol,
    CASE
        WHEN EXISTS (SELECT 1 FROM incidents i WHERE i.status='OPEN' AND i.severity IN ('HIGH','CRITICAL') AND (i.symbol=s.symbol OR i.symbol IS NULL)) THEN 'ERROR_RECONCILIATION_REQUIRED'::status_effective
        WHEN EXISTS (SELECT 1 FROM positions p WHERE p.symbol=s.symbol AND p.state='ACTIVE' AND p.protection_state='VALID' AND p.reconciliation_status='PASS') THEN 'ACTIVE'::status_effective
        WHEN s.status IN ('RISK_REJECTED','REJECTED') THEN 'REJECTED'::status_effective
        WHEN s.status IN ('BLOCKED') THEN 'BLOCKED'::status_effective
        ELSE 'NO_TRADE'::status_effective
    END AS status_effective,
    s.trace_id,
    s.reasons,
    s.created_at
FROM signals s
ORDER BY s.symbol, s.created_at DESC;

COMMIT;

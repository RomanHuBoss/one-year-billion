# Crypto Acceleration System 2026

Safety-first local/VPS project for **Bybit Linear USDT Futures / USDT Perpetual only**.

The project implements the roadmap/specification scope without frontend frameworks:

- PostgreSQL migrations, safety constraints and lineage tables.
- Python 3.11+ FastAPI backend.
- Risk engine as the hard order gate.
- Deterministic `orderLinkId`, idempotency, per-symbol lock and live-gated Bybit adapter boundary.
- Runtime live preflight for Bybit public/private/permission checks and DB-backed Go/No-Go evidence.
- YAML startup validation, Phase 0 universe validator and conservative regime classifier.
- Strategies that return `SignalCandidate` only.
- ML gate with fail-closed inference and optional scikit-learn training utilities.
- Ollama LLM news/risk gate that can only `BLOCK` or `ANNOTATE`.
- Vanilla HTML/CSS/JS dashboard; no browser-side business logic.
- Tests for critical invariants, live gates, idempotency and startup security.

## Current delivery status

Revision `1.4.0-live-gated` is a **live-gated runtime**. A live-submit endpoint exists, but it is fail-closed and cannot reach Bybit unless PostgreSQL, signed Go/No-Go evidence, 14+ days Phase 0 paper evidence, reconciliation/security/CI evidence, runtime Bybit checks, persisted approved `RiskDecision`, persistent idempotency and operator approval all pass.

Final local validation:

```bash
python scripts/validate_project.py
# 40 passed
# OK: strategies have no direct execution/Bybit imports
# OK: migration static invariants present
# OK: no obvious secrets
```

## Safety defaults

`TRADING_ENABLED=false` and `CAS_ENABLE_LIVE_SUBMIT=false` by default. Live routing stays disabled until runtime checks, PostgreSQL Go/No-Go evidence and operator approval pass.

Hard invariants implemented in code and DB migration:

1. No approved, non-expired `risk_decision_id` -> no order.
2. No verified protection -> no ACTIVE position.
3. Strategies do not import execution/Bybit modules and can return only candidates.
4. Frontend displays backend `status_effective` only.
5. Missing/stale ML model blocks ML-required strategies.
6. One pending entry per symbol is enforced in memory and DB.
7. Live startup is rejected when operator keys are unsafe, Bybit credentials are missing, Go/No-Go is absent, demo mode is enabled or `CAS_ENABLE_LIVE_SUBMIT=false`.
8. Ollama/LLM never opens trades, changes leverage or changes size.
9. HTTP ack from Bybit is not treated as fill; reconciliation/protection must follow. Unknown REST result marks `ERROR_RECONCILIATION_REQUIRED` and does not release symbol lock.

## Local run without Docker

### 1. Create Python environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create PostgreSQL database

```bash
createdb cas2026
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/cas2026"
./scripts/bootstrap_db.sh
# optional local-only demo seed:
# CAS_SEED_DEMO_DATA=true ./scripts/bootstrap_db.sh
```

### 3. Configure environment

```bash
cp .env.example .env
# edit .env manually
```

Required for operator write actions:

```bash
export OPERATOR_API_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
export READONLY_API_KEY="$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
```

Optional Ollama:

```bash
ollama serve
ollama pull llama3.1
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="llama3.1"
```

### 4. Run backend

```bash
./scripts/run_backend.sh
```

Dashboard: `http://127.0.0.1:8000/`

API docs: `http://127.0.0.1:8000/docs`

Preflight: `http://127.0.0.1:8000/api/runtime/preflight`

### 5. Run tests

```bash
python scripts/validate_project.py
```

## Live gate checklist

Before `/api/execution/live-submit` can submit to Bybit, all must be true:

```bash
export APP_ENV=prod
export TRADING_ENABLED=true
export CAS_ENABLE_LIVE_SUBMIT=true
export BYBIT_LIVE_CONFIRM=true
export BYBIT_API_KEY=<server-side-only>
export BYBIT_API_SECRET=<server-side-only>
export CAS_REQUIRE_DB_FOR_LIVE=true
export CAS_REQUIRE_LIVE_PREFLIGHT=true
export CAS_REQUIRE_GO_NOGO_FOR_LIVE=true
export CAS_GO_NOGO_PASS=true
export CAS_LIVE_APPROVED_BY=<product-owner>
export CAS_ALLOW_DEMO_ML=false
export CAS_DEMO_MODE=false
python scripts/live_preflight.py
```

DB-backed evidence is mandatory. Record it only after the actual checks are complete:

```bash
python scripts/record_go_no_go_evidence.py --type PHASE0_PAPER --status PASS --started-at 2026-05-01T00:00:00Z --ended-at 2026-05-15T00:00:00Z --metrics-json '{"reconciliation_pass_rate":1.0,"unresolved_incidents":0}'
python scripts/record_go_no_go_evidence.py --type RECONCILIATION --status PASS --metrics-json '{"pass_rate":1.0}'
python scripts/record_go_no_go_evidence.py --type SECURITY --status PASS --metrics-json '{"secret_scan":"PASS"}'
python scripts/record_go_no_go_evidence.py --type CI --status PASS --metrics-json '{"tests":40}'
python scripts/record_go_no_go_evidence.py --type GO_NO_GO --status PASS --approved-by <product-owner>
```

`python scripts/live_preflight.py` must return `status: ok`. If it returns `blocked`, live order submission is correctly disabled.

## Project tree

```text
app/
  api/                FastAPI routes, response contract, auth/idempotency/audit
  backtest/           execution-aware validation
  config/             config loader and safety validator
  core/               settings, hashing, time utilities
  db/                 PostgreSQL connection/repository helpers
  execution/          order router, idempotency, state machine, Bybit adapter boundary
  live/               live preflight and submit gate
  llm/                Ollama block/annotate-only gate
  market_data/        freshness gates and Bybit normalization
  ml/                 ML fail-closed gate, labels, training utilities
  paper_trading/      paper/shadow pipeline
  reconciliation/     reconciliation and protection checks
  regime/             conservative regime classifier
  reports/            Go/No-Go report generator
  risk_engine/        hard approval gate, sizing, cost model, liquidation checks
  schemas/            typed domain/API schemas
  security/           RBAC, redaction, startup guard
  strategies/         SignalCandidate-only strategies
frontend/             vanilla dashboard
migrations/           PostgreSQL schema and seed data
scripts/              local run/test/live-preflight utilities; no Docker
config/               YAML runtime policy
universe/             phase-limited whitelist
```

## Operational boundary

This repository can be launched locally and can be configured for live-gated operation, but final production readiness still requires external evidence: real PostgreSQL migration, real Bybit credentials/permissions, runtime preflight PASS, no unresolved HIGH/CRITICAL incidents and DB-recorded paper/shadow Go/No-Go PASS.

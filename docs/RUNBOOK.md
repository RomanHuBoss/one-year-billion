# Operator runbook

## Normal local start

```bash
source .venv/bin/activate
cp .env.example .env
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cas2026
./scripts/bootstrap_db.sh
./scripts/run_backend.sh
```

Open `http://127.0.0.1:8000/`.

## Paper pipeline

Open `/` and press **Run paper once**, or call:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/run-once
```

## Runtime/live preflight

Live-submit is disabled by default. Before any live attempt, run:

```bash
python scripts/live_preflight.py
```

The result must be:

```json
{"status": "ok"}
```

A BLOCKED result is expected until PostgreSQL, Bybit credentials, runtime specs, private account access, API-key trade permission, DB-recorded paper/reconciliation/security/CI/Go-No-Go evidence and operator approval are all present.

## Minimal live environment

```bash
export APP_ENV=prod
export DATABASE_URL=postgresql://...
export OPERATOR_API_KEY=<long-random-operator-key>
export READONLY_API_KEY=<different-long-random-readonly-key>
export BYBIT_TESTNET=true                # first use testnet
export BYBIT_API_KEY=<server-side-only>
# set BYBIT_API_SECRET to the server-side-only secret in your shell
export BYBIT_LIVE_CONFIRM=true
export TRADING_ENABLED=true
export CAS_ENABLE_LIVE_SUBMIT=true
export CAS_REQUIRE_DB_FOR_LIVE=true
export CAS_REQUIRE_LIVE_PREFLIGHT=true
export CAS_REQUIRE_GO_NOGO_FOR_LIVE=true
export CAS_GO_NOGO_PASS=true
export CAS_LIVE_APPROVED_BY=<product-owner>
export CAS_ALLOW_DEMO_ML=false
export CAS_DEMO_MODE=false
```

Production endpoint (`BYBIT_TESTNET=false`) must be enabled only after the same gate passes on testnet and after the required DB-recorded paper/shadow evidence.

## Live-submit contract

Live order route: `POST /api/execution/live-submit`.

It is locked by:

1. explicit `CAS_ENABLE_LIVE_SUBMIT=true`;
2. `TRADING_ENABLED=true` and `BYBIT_LIVE_CONFIRM=true`;
3. server-side Bybit credentials;
4. PostgreSQL availability;
5. no unresolved HIGH/CRITICAL incidents;
6. Go/No-Go approval env plus DB-recorded evidence;
7. runtime Bybit public, private and API-key permission checks;
8. persisted approved non-expired `RiskDecision` in DB;
9. deterministic `orderLinkId` and persistent idempotency key.

HTTP ack from Bybit is **not** treated as fill. The next required stage is private WS or REST reconciliation and then protection verification.

## Emergency actions

Only reduce-risk write actions exist:

- `DISABLE_TRADING`
- `CANCEL_OPEN_ENTRIES`
- `FLATTEN_REDUCE`
- `RESOLVE_INCIDENT`
- `PROPOSE_CONFIG`
- `ACTIVATE_CONFIG`

There is no force-open endpoint.

## Validation

```bash
python scripts/validate_project.py
python scripts/live_preflight.py
```

`validate_project.py` must pass locally. `live_preflight.py` must pass only in the real runtime environment.


## Recording Go/No-Go evidence

Use this only after the evidence is real. The live gate reads these rows from PostgreSQL; env flags alone are not sufficient.

```bash
python scripts/record_go_no_go_evidence.py --type PHASE0_PAPER --status PASS --started-at 2026-05-01T00:00:00Z --ended-at 2026-05-15T00:00:00Z --metrics-json '{"reconciliation_pass_rate":1.0,"unresolved_incidents":0}'
python scripts/record_go_no_go_evidence.py --type RECONCILIATION --status PASS --metrics-json '{"pass_rate":1.0}'
python scripts/record_go_no_go_evidence.py --type SECURITY --status PASS --metrics-json '{"secret_scan":"PASS"}'
python scripts/record_go_no_go_evidence.py --type CI --status PASS --metrics-json '{"tests":40}'
python scripts/record_go_no_go_evidence.py --type GO_NO_GO --status PASS --approved-by <product-owner>
```

If live-submit receives an ambiguous REST failure after reserving an order, the order is marked `ERROR_RECONCILIATION_REQUIRED`; do not retry with a new idempotency key until reconciliation confirms exchange state.

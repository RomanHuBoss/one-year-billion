# Traceability matrix

| Finding / invariant | Реализация | Тест |
|---|---|---|
| CF-02 / INV-01: нет approved risk_decision_id -> нет order | `migrations/0001_core_schema.sql`, `app/risk_engine/approval.py`, `app/execution/order_router.py` | `tests/test_risk_engine.py`, `tests/test_execution.py` |
| CF-03 / INV-02: нет verified protection -> нет ACTIVE | `positions.active_position_protected`, `app/execution/state_machine.py`, `app/reconciliation/protection_watchdog.py` | `tests/test_state_machine.py` |
| CF-04 / INV-05: stale data blocks | `app/market_data/freshness.py`, `app/risk_engine/approval.py` | `tests/test_risk_engine.py` |
| CF-06: grid не martingale | `app/regime/classifier.py`, `app/strategies/micro_grid.py` | `tests/test_strategy_architecture.py` |
| CF-07: retry не увеличивает exposure | `app/execution/idempotency.py`, `app/execution/order_router.py` | `tests/test_execution.py` |
| CF-08/CF-16: frontend не source of truth | `frontend/js/status_contract.js`, `/api/state/overview` | manual E2E + API contract |
| CF-09: ML fail-closed | `app/ml/inference.py` | `tests/test_ml_fail_closed.py` |
| CF-10: no secrets in frontend/logs | `app/security/redaction.py`, `scripts/secret_scan.py` | `scripts/secret_scan.py` |
| CF-11/CF-13: costs and realistic validation | `app/risk_engine/cost_model.py`, `app/backtest/engine.py` | `tests/test_risk_engine.py` |
| CF-14 / INV-03: strategies do not import execution | `app/strategies/*` | `scripts/check_strategy_imports.py`, `tests/test_strategy_architecture.py` |
| LLM boundary: BLOCK/ANNOTATE only | `app/llm/news_risk.py` | `tests/test_llm_boundary.py` |

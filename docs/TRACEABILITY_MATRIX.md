# Матрица трассируемости

| Finding / invariant | Реализация | Тест / проверка |
|---|---|---|
| CF-02 / INV-01: нет approved `risk_decision_id` — нет order | `migrations/0001_core_schema.sql`, `app/risk_engine/approval.py`, `app/execution/order_router.py`, `app/db/repository.py` | `tests/test_risk_engine.py`, `tests/test_execution.py`, `tests/test_live_submit_route.py` |
| CF-03 / INV-02: нет verified protection — нет ACTIVE | `positions.active_position_protected`, `app/execution/state_machine.py`, `app/reconciliation/protection_watchdog.py` | `tests/test_state_machine.py` |
| CF-04 / INV-05: stale data blocks | `app/market_data/freshness.py`, `app/risk_engine/approval.py`, `app/api/routes/runtime.py` | `tests/test_risk_engine.py`, `tests/test_market_data_ingestion.py` |
| CF-06: grid не martingale | `app/regime/classifier.py`, `app/strategies/micro_grid.py`, `config/strategy_permissions.yaml` | `tests/test_strategy_architecture.py`, `tests/test_phase_runtime.py` |
| CF-07: retry не увеличивает exposure | `app/execution/idempotency.py`, `app/execution/order_router.py`, `app/db/repository.py` | `tests/test_execution.py`, `tests/test_idempotency_hardening.py`, `tests/test_live_submit_hardening.py` |
| CF-08/CF-16: frontend не source of truth | `frontend/js/status_contract.js`, `frontend/js/app.js`, `/api/state/overview` | API contract + manual E2E; `tests/test_live_gates.py` |
| CF-09: ML fail-closed | `app/ml/inference.py`, `app/ml/model_registry.py` | `tests/test_ml_fail_closed.py` |
| CF-10: no secrets in frontend/logs | `app/security/redaction.py`, `scripts/secret_scan.py`, `.gitignore` | `scripts/secret_scan.py` |
| CF-11/CF-13: costs and realistic validation | `app/risk_engine/cost_model.py`, `app/backtest/engine.py` | `tests/test_risk_engine.py`, `tests/test_cost_model_and_backtest.py` |
| CF-14 / INV-03: strategies do not import execution | `app/strategies/*` | `scripts/check_strategy_imports.py`, `tests/test_strategy_architecture.py` |
| CF-15: rate limits/reconnect storm -> degraded/no-trade | `app/execution/rate_limiter.py`, `app/execution/bybit_adapter.py`, `app/live/preflight.py` | `tests/test_bybit_adapter_safety.py`, `tests/test_live_gates.py` |
| Live risk approval требует RBAC/idempotency | `app/api/routes/risk.py`, `app/execution/idempotency.py` | `tests/test_live_risk_approval_gates.py` |
| LLM boundary: только BLOCK/ANNOTATE/UNAVAILABLE | `app/llm/news_risk.py`, `app/llm/ollama_client.py` | `tests/test_llm_boundary.py` |
| CLI-запуск из корня | `main.py`, `scripts/run_backend.sh`, `README.md` | `python main.py --help`, `python main.py validate` |

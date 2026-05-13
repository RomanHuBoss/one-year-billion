# Финальный отчет по тотальной проверке и доработке проекта

## Статус

**Итоговый статус:** `paper-ready / technical-live-ready / live-gated`.

Код прошел локальные проверки и hard-invariant тесты. Реальный live остается заблокирован до внешних gates: PostgreSQL instance с миграциями, реальные Bybit credentials/permissions, runtime preflight PASS, private WebSocket/reconciliation, 14+ дней paper/shadow evidence, подписанный Go/No-Go PASS и unresolved CRITICAL/HIGH = 0.

## Что проверено

- Архитектура слоев `market_data`, `regime`, `strategies`, `ml`, `risk_engine`, `execution`, `reconciliation`, `api`, `frontend`.
- Отсутствие прямого маршрута `strategies -> Bybit/execution/order_router`.
- CLI-entrypoints: `python main.py`, `validate`, `preflight --mode testnet/live`, `serve --mode testnet/live`.
- Data foundation: Bybit linear scope, runtime specs, TTL/freshness gates, hashes, redaction, config hash, trace id.
- Risk engine: stop/risk/rounding/minNotional/costs/leverage/liquidation/daily-weekly limits/net edge.
- Execution: deterministic `orderLinkId`, idempotency, symbol lock, retry safety, HTTP ack != fill, reconciliation/protection gates.
- Regime/strategy permissions: conservative priority, grid only in RANGE, breakout only after confirmation, carry/stat-arb shadow-only Phase 0/1.
- ML: ALLOW/BLOCK/UNAVAILABLE gate only, stale/missing/drift fail-closed.
- API/frontend: typed envelopes, request_id/server_time/trace_id, RBAC, idempotency for writes, backend source of truth.
- Security: server-side secrets, secret scan, live flags fail-closed, no Bybit keys in frontend.
- DB migrations: orders require approved non-expired risk decision, unique client/exchange ids, ACTIVE requires protection/reconciliation, audit/evidence tables.
- Documentation: Russian README/runbook/operator instructions and explicit live-block warnings.

## Что исправлено в этой редакции

| Область | Исправление | Файлы |
|---|---|---|
| Backend API diagnostics | HTTP 401/403 от Bybit/operator API нормализуется в безопасный `BybitAPIError` с reason `invalid_api_key_http_401`/auth-failed без утечки ключей. | `app/execution/bybit_adapter.py` |
| Операторский frontend | Добавлено поле **API-доступ** в верхней панели. Read-запросы dashboard/commands/jobs/paper получают `x-api-key`, если оператор его ввел. | `frontend/index.html`, `frontend/js/app.js`, `frontend/css/styles.css` |
| UI ошибки | `Ошибка API 401: invalid_api_key` теперь объясняет, что это backend `OPERATOR_API_KEY`/`READONLY_API_KEY`, а не Bybit key. | `frontend/js/api_client.js`, `frontend/js/app.js` |
| Тесты | Добавлены проверки нормализации 401 и frontend-auth behavior. | `tests/test_api_401_diagnostics.py` |
| Документация | Добавлен разбор `API 401: invalid_api_key` и различие backend key vs Bybit private API auth. | `README.md`, `docs/OPERATOR_MANUAL.md`, `docs/RUNBOOK.md` |

## Запущенные проверки

```text
python -m pytest -q
125 passed, 1 warning

python main.py validate
compileall: OK
pytest: 125 passed, 1 warning
scripts/check_strategy_imports.py: OK
scripts/check_architecture.py: OK
scripts/check_migrations_static.py: OK
scripts/secret_scan.py: OK

python main.py preflight --mode testnet
status=blocked
reasons=[cannot_verify_unresolved_incidents_without_db, database_required_for_testnet_preflight, testnet_bybit_credentials_missing]

python main.py preflight --mode live
status=blocked
reasons=[cannot_verify_unresolved_incidents_without_db, cas_enable_live_submit_false, database_required_for_live, go_no_go_evidence_db_required, go_no_go_pass_and_approver_required, trading_flags_or_bybit_credentials_missing]
```

`blocked` для testnet/live preflight в песочнице является корректным fail-closed поведением: нет PostgreSQL и реальных credentials/evidence.

## Таблица соответствия specification / roadmap

| Требование | Статус | Файл/модуль | Тест/доказательство |
|---|---:|---|---|
| Нет approved non-expired `risk_decision_id` -> нет order | PASS | `app/risk_engine/approval.py`, `app/execution/order_router.py`, `migrations/0001_core_schema.sql`, `0003_hard_invariants.sql` | `test_live_risk_approval_gates.py`, `test_migration_hard_invariants_static.py`, `check_migrations_static.py` |
| Нет verified protection -> нет ACTIVE | PASS | `app/execution/state_machine.py`, `app/reconciliation/protection_watchdog.py`, migrations `positions` CHECK | `test_state_machine.py`, `test_execution.py`, migration static checks |
| Strategy returns only `SignalCandidate`; no Bybit/execution import | PASS | `app/strategies/*`, `scripts/check_strategy_imports.py` | `test_strategy_architecture.py`, `check_strategy_imports.py` |
| Frontend не source of truth | PASS | `frontend/js/status_contract.js`, `frontend/js/app.js`, `app/api/routes/operator.py` | `test_db_status_contract_static.py`, `check_architecture.py` |
| Stale data -> NO_TRADE/BLOCKED до risk approval | PASS | `app/market_data/freshness.py`, `app/risk_engine/approval.py`, `app/regime/classifier.py` | `test_market_data_ingestion.py`, `test_risk_engine.py`, `test_regime_classifier.py` |
| Target equity только analytics/stress | PASS | no target imports in `risk_engine`/`execution`; architecture check | `check_architecture.py` |
| Carry/stat-arb Phase 0/1 no live route | PASS | `app/strategies/carry_shadow.py`, `statarb_shadow.py`, `app/config/phase_validator.py`, `app/execution/order_router.py` | `test_shadow_scanners.py`, `test_phase_runtime.py`, `test_strategy_gates.py` |
| Manual override only risk-reducing | PASS | `app/api/routes/actions.py`, migrations `manual_request_log` CHECK | `test_manual_actions_safety.py`, migration static checks |
| Live до Go/No-Go PASS и unresolved HIGH/CRITICAL=0 невозможен | PASS | `app/live/preflight.py`, `app/live/gate.py`, `app/db/repository.py` | `test_live_gates.py`, `test_startup_guard.py` |
| Только Bybit V5 `category=linear` / USDT futures | PASS | `config/system.yaml`, `app/execution/bybit_adapter.py`, `universe/dynamic_whitelist.py` | `test_config_forbidden_scope.py`, `test_bybit_adapter_safety.py` |
| API 401 diagnostics | PASS | `app/execution/bybit_adapter.py`, `frontend/js/api_client.js`, `frontend/js/app.js` | `test_api_401_diagnostics.py` |

## Оставшиеся blockers

| Severity | Причина | Что требуется для закрытия |
|---|---|---|
| HIGH | PostgreSQL недоступен в песочнице, миграции не применены к реальной БД. | Поднять PostgreSQL/TimescaleDB, выполнить `python scripts/bootstrap_db.py`, повторить testnet preflight. |
| HIGH | Нет реальных Bybit testnet/live credentials и runtime private API проверки. | Заполнить `.env`, проверить endpoint testnet/live, IP whitelist, permissions, account mode, wallet/positions. |
| HIGH | Нет 14+ дней Phase 0 paper/shadow evidence в БД. | Накопить evidence `PHASE0_PAPER`, `RECONCILIATION=PASS`, без unresolved incidents. |
| HIGH | Нет подписанного `GO_NO_GO=PASS`. | Записать evidence через `record_go_no_go_evidence.py` с `approved_by`. |
| HIGH | Private WebSocket/reconciliation нельзя проверить в песочнице. | Проверить на testnet/VPS с реальными ключами и журналом reconciliation. |

## Коммит

```text
feat: подготовить проект к test/live-ready состоянию по specification и roadmap

- нормализовать API 401 invalid_api_key без утечки секретов
- добавить ввод backend API-доступа в операторский dashboard
- передавать x-api-key для read/write запросов операторского интерфейса
- добавить тесты 401 diagnostics и frontend-auth behavior
- обновить русскоязычную документацию по backend key vs Bybit private API
```

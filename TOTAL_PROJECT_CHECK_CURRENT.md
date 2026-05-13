# Текущая проверка total_project_check — редакция 8.2

## Результат

Проект приведен к состоянию **technical-live-ready / live-gated**: локальный запуск, paper/testnet-preflight и проверочный pipeline работают; live-submit остается fail-closed до внешних gate: PostgreSQL, Bybit runtime/private API, 14+ дней Phase 0 paper/shadow evidence, reconciliation/security/CI evidence, подписанный Go/No-Go PASS и unresolved CRITICAL/HIGH = 0.

## Что было проверено

- Архитектура слоев: `market_data`, `regime`, `strategies`, `ml`, `risk_engine`, `execution`, `reconciliation`, `api`, `frontend`.
- Отсутствие прямого пути strategy -> Bybit/execution/order router.
- Risk engine как hard gate: approved non-expired `risk_decision_id` обязателен для order.
- Execution safety: deterministic `orderLinkId`, idempotency, per-symbol lock, HTTP ack != fill, reconciliation/protection перед ACTIVE.
- DB hard-invariants: approved risk decision, unique idempotency/client order, ACTIVE только с protection/reconciliation, lineage.
- Runtime data gates: stale instruments/account/orderbook/funding fail-closed.
- Phase 0 scope: BTCUSDT/ETHUSDT/SOLUSDT; carry/stat-arb только shadow; DCA/martingale/spot/inverse/options/copy/signal/portfolio запрещены.
- Frontend source-of-truth: только backend `status_effective`, без ключей и без Bybit-вызовов.
- Security: server-side secrets, redaction, secret scan, unsafe defaults blocked.
- Econometrics/math: costs, net edge, no gross-only live basis, ML leakage checks, same-bar ambiguity conservative.
- CLI: `python main.py`, `validate`, `preflight --mode testnet`, `preflight --mode live`, `serve --mode testnet/live`.

## Исправления редакции 8.2

- Усилен `app/risk_engine/approval.py`: `NaN`, `inf` и невалидные числовые значения `SignalCandidate`, `RiskConfig`, `CostModel` теперь fail-closed приводят к rejected `RiskDecision`.
- Добавлены regression-тесты в `tests/test_risk_engine.py`:
  - `test_nan_signal_edge_rejected_fail_closed`;
  - `test_infinite_entry_price_rejected_fail_closed`;
  - `test_negative_cost_model_rejected_fail_closed`;
  - `test_nonfinite_risk_config_rejected_fail_closed`.
- Актуализированы счетчики тестов в `README.md`, `docs/RUNBOOK.md`, `docs/GO_NO_GO.md`.
- Добавлены записи редакции 8.2 в `TOTAL_PROJECT_CHECK_REPORT.md` и `DELIVERY_REPORT.md`.

## Запущенные проверки

```text
python main.py validate
```

Результат:

```text
compileall: PASS
pytest: 112 passed, 1 warning
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS
```

```text
python main.py preflight --mode testnet
```

Результат в песочнице: `blocked` по ожидаемым внешним причинам: нет PostgreSQL, нет testnet Bybit credentials, нельзя проверить unresolved incidents без БД.

```text
python main.py preflight --mode live
```

Результат в песочнице: `blocked` по ожидаемым live-gate причинам: нет PostgreSQL, Go/No-Go evidence, live flags/credentials, unresolved incidents cannot be verified.

## Что нельзя подтвердить внутри песочницы

- Реальные Bybit API keys, permissions, IP whitelist и account mode.
- Реальные runtime instruments testnet/prod на конкретном аккаунте.
- PostgreSQL instance пользователя с примененными migrations.
- Private WebSocket, реальные fills/positions и reconciliation на бирже.
- 14+ дней Phase 0 paper/shadow evidence.
- Подписанный Go/No-Go PASS в production-БД.

## Финальный статус

- Локальный запуск: PASS.
- Testnet/paper готовность: технически подготовлено, но preflight требует внешнюю БД и testnet credentials.
- Live: **не разрешен** до прохождения внешних gate. Это корректное поведение; unsafe live-submit технически заблокирован.

# Текущая проверка total_project_check — редакция 8.4

## Результат

Проект находится в состоянии **test-ready / paper-ready для локального smoke / technical-live-ready как live-gated кодовая база**. Фактический live остается **live-blocked**, пока внешняя среда не подтвердит PostgreSQL, Bybit testnet/prod runtime, private permissions, 14+ дней Phase 0 paper/shadow evidence, reconciliation/security/CI evidence, подписанный Go/No-Go PASS и unresolved CRITICAL/HIGH = 0.

## Что проверено

- Архитектура слоев: `market_data`, `regime`, `strategies`, `ml`, `risk_engine`, `execution`, `reconciliation`, `api`, `frontend`.
- Отсутствие прямого пути `strategy -> Bybit/execution/order router`.
- Risk engine как hard gate: approved non-expired `risk_decision_id` обязателен для order.
- Execution safety: deterministic `orderLinkId`, idempotency, per-symbol lock, HTTP ack != fill, reconciliation/protection перед ACTIVE.
- DB hard-invariants: approved risk decision, unique idempotency/client order, ACTIVE только с protection/reconciliation, lineage.
- Runtime data gates: stale instruments/account/orderbook/funding fail-closed.
- Phase 0 scope: BTCUSDT/ETHUSDT/SOLUSDT; carry/stat-arb только shadow; DCA/martingale/spot/inverse/options/copy/signal/portfolio запрещены.
- Frontend source-of-truth: только серверные `status_effective` и backend-status из API, без ключей, без Bybit-вызовов и без локального вывода статуса из `risk.approved`.
- Security: server-side secrets, redaction, secret scan, unsafe defaults blocked.
- Econometrics/math: costs, net edge, no gross-only live basis, ML leakage checks, same-bar ambiguity conservative.
- CLI: `python main.py`, `validate`, `preflight --mode testnet`, `preflight --mode live`, `serve --mode testnet/live`.

## Исправления редакции 8.4

- Исправлен `app/paper_trading/pipeline.py`: paper endpoint теперь возвращает явные `status` и `reasons` по каждому paper-решению. Это убирает необходимость для браузера локально выводить статус из `risk.approved`.
- Исправлен `frontend/js/app.js`: paper-резюме отображает только готовый backend-status; fallback помечает отсутствие серверного статуса как `status_from_backend_missing`, а не строит локальную бизнес-логику.
- Усилен `scripts/check_architecture.py`: добавлен static guard против локального frontend-вывода статуса из `row.risk.approved` / `risk_approved` ternary.
- Добавлен regression-тест `test_paper_summary_does_not_derive_status_from_frontend_risk_approval`.
- Дополнительно русифицированы пользовательские подписи в операторском frontend: `source of truth`, `backend`, `Job`, `Exit`, `safe-actions` заменены на русские формулировки, не меняя технических идентификаторов.

## Запущенные проверки

```text
python main.py validate
```

Результат:

```text
compileall: PASS
pytest: 116 passed, 1 warning
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

## Итоговый статус

- Локальный запуск: PASS.
- Testnet/paper готовность: технически подготовлено, но testnet preflight требует внешнюю БД и testnet credentials.
- Technical-live-ready: кодовая база готова как fail-closed/live-gated система.
- Live: **не разрешен** до прохождения внешних gate. Это корректное поведение; unsafe live-submit технически заблокирован.

## Дополнение 8.6 — исправление validate в APP_ENV=testnet

- Устранен DB CHECK conflict при audit rejected config activation: unsafe risk-up попытка логируется как `REJECTED_UNSAFE_ACTION`, а не как исполнимый `ACTIVATE_CONFIG`.
- Regression-тесты operator/paper/runtime endpoints используют `READONLY_API_KEY`, поэтому `python main.py validate` проходит как в `APP_ENV=local`, так и в `APP_ENV=testnet`.
- Operator dashboard в testnet-safe окружении показывает `Безопасный testnet/local режим`.
- Проверка: `python main.py validate` при `APP_ENV=testnet` — `116 passed, 1 warning`; architecture/migrations/secret scan — PASS.

# Total project check — отчет по обработке

## Нормативная база

Проверка и доработка выполнены по `prompts/total_project_check.txt`, `docs/specification.docx` и `docs/roadmap.docx`. При конфликте приоритет отдан спецификации.

## Что проверено

- Архитектура слоев `market_data`, `regime`, `strategies`, `ml`, `risk_engine`, `execution`, `reconciliation`, `api`, `frontend`.
- Корневой CLI: `python main.py`, `validate`, `preflight --mode testnet`, `preflight --mode live`, `serve`.
- Risk engine: stale data, missing stop, invalid stop, minQty/minNotional, qtyStep rounding, costs, daily/weekly caps, portfolio exposure, beta-adjusted exposure, target-equity isolation.
- Execution: deterministic `orderLinkId`, idempotency, per-symbol lock, live-submit gate, paper/live separation, `ack_is_fill=false`.
- DB constraints: `orders.risk_decision_id`, approved/non-expired risk decision, `client_order_id`, `exchange_fill_id`, ACTIVE/protection state, manual actions, lineage.
- Regime/strategies: grid only in RANGE, breakout only with confirmations, carry/stat-arb shadow-only in Phase 0/1, no strategy direct exchange import.
- ML/backtest/econometrics: fail-closed ML, leakage guards, same-bar TP/SL ambiguity, costs/net-edge checks.
- API/frontend/security: RBAC/idempotency for writes, status source-of-truth backend-only, no Bybit/secrets in frontend, secret scan.
- Документация: README, runbook, Go/No-Go, traceability, `.env.example`.

## Что исправлено

- Добавлена миграция `migrations/0003_hard_invariants.sql` для защиты от прямого SQL bypass:
  - approved `risk_decisions` требуют положительного sizing и `max_loss_if_stop <= risk_budget`;
  - `orders.qty` и расчетный notional не могут превышать approved sizing;
  - `signals.feature_hash` должен совпадать с `risk_decisions.feature_hash`;
  - `SHADOW_SIGNAL`, `REJECTED`, `RISK_REJECTED` не имеют live-route;
  - запрещены martingale/DCA/spot/inverse/options/copy/signal/portfolio стратегии на уровне DB;
  - ACTIVE position не может быть flat/zero-qty;
  - config proposal/activation не может повышать risk.
- `scripts/bootstrap_db.sh` теперь применяет все core-миграции автоматически и пропускает demo-seed без `CAS_SEED_DEMO_DATA=true`.
- `scripts/check_migrations_static.py` теперь проверяет все SQL-миграции, а не только `0001_core_schema.sql`.
- Добавлены regression-тесты `tests/test_migration_hard_invariants_static.py`.
- Обновлены README, `docs/TRACEABILITY_MATRIX.md`, `docs/GO_NO_GO.md`, `DELIVERY_REPORT.md`.

## Измененные файлы

- `migrations/0003_hard_invariants.sql` — новая hard-invariant migration.
- `scripts/bootstrap_db.sh` — применение всех core-миграций.
- `scripts/check_migrations_static.py` — static check всех migration-инвариантов.
- `tests/test_migration_hard_invariants_static.py` — новые regression-тесты.
- `README.md` — актуализирован запуск PostgreSQL и количество тестов.
- `docs/TRACEABILITY_MATRIX.md` — добавлена трассировка DB hard invariants.
- `docs/GO_NO_GO.md` — актуализировано количество тестов.
- `DELIVERY_REPORT.md` — добавлен блок редакции 2.0.

## Запущенные проверки

```text
python main.py validate
```

Результат:

```text
compileall: PASS
pytest: 80 passed
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS
```

Дополнительно:

```text
python main.py preflight --mode testnet: blocked fail-closed без PostgreSQL/ключей/Go-No-Go
python main.py preflight --mode live: blocked fail-closed без PostgreSQL/ключей/Go-No-Go
```

## Невозможно подтвердить в песочнице

- Реальные Bybit API keys и permissions.
- Account mode и реальные runtime instruments на конкретном аккаунте.
- PostgreSQL instance с примененными миграциями.
- Private WebSocket, fills, positions и reconciliation на реальной бирже.
- 14+ дней Phase 0 paper/shadow evidence.
- Подписанный Go/No-Go PASS и отсутствие unresolved CRITICAL/HIGH incidents в production-БД.

## Итоговый статус

- `test-ready`: да.
- `paper-ready`: да, после подключения PostgreSQL и runtime data источников.
- `technical-live-ready`: да, как live-gated кодовая база.
- `live-blocked`: да, до внешних gates. Это ожидаемое безопасное состояние.

## Оставшиеся blockers

| Severity | Причина | Что требуется для закрытия |
|---|---|---|
| HIGH | Нет подключенной production/testnet PostgreSQL в песочнице | Поднять БД, применить migrations, проверить DB constraints |
| HIGH | Нет реальных Bybit keys/permissions/account mode/runtime specs | Пройти `python main.py preflight --mode testnet` и затем live preflight |
| HIGH | Нет 14+ дней paper/shadow evidence | Накопить evidence и записать в `go_no_go_evidence` |
| HIGH | Нет подписанного Go/No-Go PASS | Заполнить `docs/GO_NO_GO.md`, записать `GO_NO_GO=PASS` с `approved_by` |

## Текст коммита

```text
feat: подготовить проект к test/live-ready состоянию по specification и roadmap

- усилить PostgreSQL hard-invariants против SQL bypass risk/execution gates
- добавить миграцию 0003 с проверкой approved sizing, signal/risk lineage и ACTIVE protection
- запретить risk-up config activation/proposal на уровне DB
- обновить bootstrap_db для применения всех core-миграций
- расширить migration static checks и добавить regression-тесты
- актуализировать README, traceability, Go/No-Go и delivery report
```

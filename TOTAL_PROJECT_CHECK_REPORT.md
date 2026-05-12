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
pytest: 87 passed
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


---

## Редакция 3.0 — дополнительная проверка total_project_check

Дата проверки: 2026-05-12.

### Найденные и исправленные дефекты

1. `app/risk_engine/position_sizing.py`: effective leverage теперь рассчитывается как `(существующая абсолютная портфельная экспозиция + новая заявка) / equity`, а не только по новой заявке. Это закрывает обход, при котором несколько небольших заявок могли пройти risk gate по отдельности, но суммарно превысить leverage cap.
2. `app/risk_engine/approval.py`: добавлена hard-проверка суммарной portfolio exposure через `max_effective_leverage` даже без отдельного YAML portfolio cap; beta-adjusted exposure теперь также имеет fail-closed default cap через equity * max_effective_leverage.
3. `app/strategies/micro_grid.py`: micro-grid больше не использует ATR как замену range bounds. Без явного `range_width_bps` стратегия не генерирует `SignalCandidate`, чтобы grid не превращался в скрытое усреднение/DCA против движения.
4. `app/execution/bybit_adapter.py`: emergency reduce-only market exit теперь выставляет `closeOnTrigger=True` вместе с `reduceOnly=True`.
5. Добавлены regression-тесты на portfolio leverage, beta exposure, обязательность explicit range width для micro-grid и `closeOnTrigger` на reduce-only exit.

### Измененные файлы редакции 3.0

- `app/risk_engine/position_sizing.py`
- `app/risk_engine/approval.py`
- `app/strategies/micro_grid.py`
- `app/execution/bybit_adapter.py`
- `tests/test_risk_engine.py`
- `tests/test_strategy_gates.py`
- `tests/test_bybit_adapter_safety.py`
- `TOTAL_PROJECT_CHECK_REPORT.md`
- `DELIVERY_REPORT.md`

### Проверки редакции 3.0

```text
python -m pytest -q
87 passed

python main.py validate
compileall: PASS
pytest: 87 passed
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS

python main.py preflight --mode testnet
blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence
```

### Итог редакции 3.0

Статус не меняется: `test-ready`, `paper-ready` после подключения PostgreSQL/runtime data, `technical-live-ready` как live-gated кодовая база, `live-blocked` до внешних gates.


---

## Редакция 4.0 — shadow scanners и paper/shadow evidence

Дата проверки: 2026-05-12.

### Найденные и исправленные дефекты

1. `app/strategies/carry_shadow.py`: scanner больше не является пустой заглушкой. Он генерирует только `shadow_only=True` кандидаты для измерения funding/carry edge, с evidence, stop-proxy, invalidator и явной пометкой отсутствия live-route в Phase 0/1.
2. `app/strategies/statarb_shadow.py`: scanner теперь создает только `shadow_only=True` кандидаты для накопления контекста pair stat-arb в RANGE/LOW_VOL без двухногого исполнения.
3. `app/strategies/orchestrator.py`: добавлен режим `include_shadow`, чтобы runtime live-orchestrator оставался без shadow-маршрута, а paper/shadow pipeline мог собирать evidence.
4. `app/paper_trading/pipeline.py`: shadow-кандидаты больше не отправляются в risk/execution, а фиксируются как `status=shadow_signal` с reason `shadow_only_no_live_execution_path`.
5. `tests/test_shadow_scanners.py`: добавлены regression-тесты, подтверждающие, что shadow scanners генерируют только shadow-кандидаты и что такой candidate не может пройти risk/order route.

### Проверки редакции 4.0

```text
python main.py validate
compileall: PASS
pytest: 87 passed
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS

python main.py preflight --mode testnet
blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence

python main.py preflight --mode live
blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence
```

### Итог редакции 4.0

Статус проекта: `test-ready`; `paper-ready` после подключения PostgreSQL/runtime data; `technical-live-ready` как live-gated кодовая база; `live-blocked` до внешних gates.

---

## Редакция 5.0 — операторский модуль и руководство оператора

Дата проверки: 2026-05-12.

### Причина доработки

Предыдущий dashboard был технически корректен, но непригоден как рабочий экран оператора: он показывал сырые JSON-блоки и требовал от пользователя разбираться в структуре backend-ответов. Для реальной эксплуатации оператору нужен понятный экран: что сейчас происходит, почему live заблокирован, что делать дальше и какие действия безопасны.

### Исправления

1. Добавлен `app/api/routes/operator.py`: backend формирует человекочитаемый operator-dashboard model, включая hero-status, readiness cards, blockers, live-transition steps, Phase 0 limits, safe actions и diagnostics.
2. `app/main.py`: подключен новый operator router.
3. `frontend/index.html`, `frontend/css/styles.css`, `frontend/js/app.js`: UI полностью переработан. Старые raw JSON panels заменены на современный операторский модуль. Сырой JSON оставлен только в скрытом блоке "Техническая диагностика".
4. Frontend продолжает использовать backend `status_effective` как источник истины и не рассчитывает торговые статусы, size, leverage или risk budget.
5. Добавлены безопасные action cards с обязательным `OPERATOR_API_KEY`, reason и idempotency key. UI не содержит кнопки открытия позиции.
6. Добавлены `docs/OPERATOR_MANUAL.md` и `docs/OPERATOR_MANUAL.docx` с пошаговой инструкцией для оператора.
7. Добавлены тесты `tests/test_operator_module.py`, которые проверяют endpoint операторской модели и отсутствие старых raw JSON панелей.

### Проверки

```text
python main.py validate
compileall: PASS
pytest: 89 passed
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS

python main.py preflight --mode testnet
blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence

python main.py preflight --mode live
blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence
```

DOCX-руководство сгенерировано и визуально проверено через render_docx: 4 страницы, без обрезки текста, наложений и поврежденных таблиц.

### Итог

Операторский контур стал пригодным для реального тестирования человеком: по экрану понятно, что делать дальше, когда нельзя торговать, какие настройки безопасны, какие проверки обязательны и почему live остается заблокированным до Go/No-Go PASS.

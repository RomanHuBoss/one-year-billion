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

## Редакция 5.0 — контекстная справка в операторском модуле

Проблема: операторский экран оставался недостаточно самообъясняющим; по статусам `blocked`, `NO_TRADE`, `stale_market`, `Live gate закрыт` было трудно понять, является ли это ошибкой или безопасным штатным поведением.

Исправление: добавлен frontend-модуль `frontend/js/context_help.js`. Теперь любой основной компонент с атрибутом `data-help` поддерживает правый клик → «Вызвать справку». Диалог строится по контексту компонента и текущему backend payload: карточки допуска, шаги preflight, символы, причины, safe-actions и blockers объясняются раздельно. Это не меняет source of truth: бизнес-статусы по-прежнему приходят из backend, frontend только расшифровывает их для оператора.

Acceptance evidence:

- `python main.py validate` — PASS, 90 passed.
- JS syntax check для `frontend/js/context_help.js` и `frontend/js/app.js` — PASS.
- Live/testnet preflight остаются fail-closed без PostgreSQL, Bybit runtime и Go/No-Go PASS.

## Редакция: operator-command-center

Проблема: оператору приходилось копировать команды из интерфейса в терминал, включая `./scripts/bootstrap_db.sh`, что снижало понятность работы и создавало ощущение, что система «ничего не делает».

Решение:

- shell-команда bootstrap заменена на `scripts/bootstrap_db.py`;
- операторский интерфейс получил контролируемый backend command-center;
- браузер не запускает произвольные команды, а вызывает allowlisted Python jobs backend;
- все write-запуски требуют operator key, idempotency key и причину;
- stdout/stderr показываются оператору прямо в интерфейсе;
- live-submit этим механизмом не включается и не обходится.

Статус проверки: `python main.py validate` — PASS, 93 теста пройдены.

## Дополнение: диагностика Bybit private API

Блокировка testnet preflight с public API OK и private API FAIL теперь не маскируется как `RuntimeError`. Preflight возвращает конкретную безопасную диагностику по endpoint/check и operator hints. Это сохраняет fail-closed поведение и делает операторский экран понятным для исправления testnet keys/permissions/IP whitelist.

---

## Редакция 8.0 — дополнительная hardening-проверка runtime specs / market snapshot

Дата проверки: 2026-05-13.

### Найденные и исправленные дефекты

1. `app/risk_engine/approval.py`: runtime specs теперь fail-closed требуют строго положительные `tick_size`, `qty_step`, `min_qty`, `min_notional`, `max_leverage` и конечные числовые значения. Нулевые `min_qty`/`min_notional` больше не проходят как технически допустимые.
2. `app/risk_engine/approval.py`: добавлен hard-gate `invalid_market_snapshot` для некорректного top-of-book (`bid1 <= 0`, `ask1 <= 0`, `ask1 < bid1`, отрицательный spread/depth, NaN/inf). Это закрывает возможность получить искусственно завышенный `expected_net_edge_bps` из-за отрицательного spread.
3. `app/risk_engine/approval.py`: добавлены проверки `invalid_account_equity` и `invalid_account_balance`, чтобы sizing не мог рассчитываться при нулевом/некорректном equity или отрицательном available balance.
4. `app/config/validator.py`: отрицательные значения costs/liquidity/risk-параметров (`slippage_buffer_bps`, `safety_buffer_bps`, `max_spread_bps`, `min_depth_usdt`, `reserve_cash_pct`, `min_liq_distance_pct` и др.) теперь отклоняются на старте конфигурации.
5. `migrations/0001_core_schema.sql` и новая `migrations/0005_positive_runtime_specs.sql`: DB-level constraint `instruments_positive_specs` теперь требует `min_qty > 0`, `min_notional > 0`, `max_leverage > 0` для новых и уже существующих БД.

### Измененные файлы редакции 8.0

- `app/risk_engine/approval.py`
- `app/config/validator.py`
- `migrations/0001_core_schema.sql`
- `migrations/0005_positive_runtime_specs.sql`
- `scripts/check_migrations_static.py`
- `tests/test_risk_engine.py`
- `tests/test_config_validator.py`
- `tests/test_migration_hard_invariants_static.py`
- `TOTAL_PROJECT_CHECK_REPORT.md`
- `DELIVERY_REPORT.md`
- `docs/TRACEABILITY_MATRIX.md`
- `docs/GO_NO_GO.md`

### Проверки редакции 8.0

```text
python main.py validate
compileall: PASS
pytest: 108 passed, 1 warning
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS

python main.py --help: PASS
python main.py serve --help: PASS
python main.py preflight --mode testnet: blocked fail-closed без PostgreSQL/Bybit keys
python main.py preflight --mode live: blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence
```

### Итог редакции 8.0

Статус проекта: `test-ready`; `paper-ready` после подключения PostgreSQL и runtime data; `technical-live-ready` как live-gated кодовая база; фактический live остается `live-blocked` до внешних gates.

---

## Редакция 8.1 — hardening Phase 0 caps и текущая проверка

Дата проверки: 2026-05-13.

### Найденный и исправленный дефект

`app/config/validator.py` раньше проверял, что risk/leverage default не выше absolute max, но не закреплял сами верхние Phase 0 caps из спецификации/roadmap. Это оставляло конфигурационный путь, при котором в YAML можно было поднять `risk_pct_absolute_max`, `max_effective_leverage_absolute` или дневной turnover без явного runtime-доказательства.

### Исправление

- Для Phase 0 валидатор теперь fail-closed отклоняет:
  - `risk_pct_default > 0.015`;
  - `risk_pct_absolute_max > 0.015`;
  - `max_effective_leverage > 3.0`;
  - `max_effective_leverage_absolute > 5.0`;
  - `turnover_round_turns_per_day > 4`.
- Добавлены regression-тесты на каждый новый hard cap.

### Измененные файлы редакции 8.1

- `app/config/validator.py`
- `tests/test_config_validator.py`
- `README.md`
- `docs/GO_NO_GO.md`
- `DELIVERY_REPORT.md`
- `TOTAL_PROJECT_CHECK_REPORT.md`

### Проверки редакции 8.1

```text
python main.py validate
compileall: PASS
pytest: 108 passed, 1 warning
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS

node --check frontend/js/api_client.js: PASS
node --check frontend/js/app.js: PASS
node --check frontend/js/context_help.js: PASS
node --check frontend/js/status_contract.js: PASS

python main.py preflight --mode testnet: blocked fail-closed без PostgreSQL/Bybit keys
python main.py preflight --mode live: blocked fail-closed без PostgreSQL/Bybit keys/Go-No-Go evidence
```

### Итог редакции 8.1

Статус проекта: `test-ready`; `paper-ready` после подключения PostgreSQL и runtime data; `technical-live-ready` как live-gated кодовая база; фактический live остается `live-blocked` до внешних gates.



## Редакция 8.2 — numeric fail-closed hardening

Дополнительно проверены числовые входы `SignalCandidate`, `RiskConfig` и `CostModel`. `NaN`, `inf`, отрицательные комиссии/буферы и невалидные risk-config значения теперь не могут пройти через сравнения Python и приводят к rejected `RiskDecision` с причинами `invalid_signal_numeric_value`, `invalid_risk_config` или `invalid_cost_model`. Добавлены regression-тесты hard-invariants.

---

## Редакция 8.3 — hardening SignalCandidate lineage и live RiskDecision payload integrity

Дата проверки: 2026-05-13.

### Найденные и исправленные дефекты

1. `app/risk_engine/approval.py`: risk approval мог вернуть общий rejected по missing evidence, но не имел отдельного hard-reason для неполной lineage-связки candidate. Добавлена проверка `regime_id`, `feature_id`, `required_data` с reason `incomplete_signal_lineage`.
2. `app/execution/order_router.py`: in-memory/paper route слишком доверял объекту `RiskDecision`, если `approved=True`. Добавлены повторные проверки evidence/lineage и `max_loss_if_stop <= risk_budget` перед созданием `OrderIntent`.
3. `app/db/repository.py`: live route теперь дополнительно сверяет sizing из HTTP payload с persisted `risk_decisions.sizing_json` до insert в `orders`. DB trigger остается последней линией обороны, но подмена payload блокируется раньше.
4. Тестовые fixtures live-submit/order-router приведены к обязательной полной модели `SignalCandidate`.

### Проверки редакции 8.3

```text
python main.py validate
compileall: PASS
pytest: 115 passed, 1 warning
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS

python main.py preflight --mode testnet
blocked: нет PostgreSQL, нет testnet Bybit credentials, нельзя проверить unresolved incidents без БД

python main.py preflight --mode live
blocked: нет PostgreSQL, нет live flags/credentials, нет Go/No-Go evidence, нельзя проверить unresolved incidents без БД
```

### Итог редакции 8.3

Статус проекта не меняется: `test-ready`, `paper-ready` после подключения PostgreSQL/runtime data, `technical-live-ready` как live-gated кодовая база, `live-blocked` до внешних gates.


## Редакция 8.4 — frontend source-of-truth hardening для paper-резюме

### Исправления

- `app/paper_trading/pipeline.py`: backend возвращает явный `status`/`reasons` для paper-решений.
- `frontend/js/app.js`: удален локальный вывод статуса из `risk.approved`; paper-резюме только отображает backend-status.
- `scripts/check_architecture.py`: добавлена static-проверка против повторного появления frontend status-derivation.
- `tests/test_operator_module.py`: добавлен regression-тест source-of-truth для paper summary.

### Проверки

```text
python main.py validate
compileall: PASS
pytest: 116 passed, 1 warning
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS
```

`python main.py preflight --mode testnet` и `python main.py preflight --mode live` в песочнице корректно возвращают `blocked` без внешних PostgreSQL/Bybit/Go-No-Go gate.

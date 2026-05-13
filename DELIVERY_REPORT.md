# Отчет о поставке — total_project_check revision 1.9

## Статус

Проект доработан до состояния **live-gated runtime** для локального запуска, testnet-проверок и подготовки к live-эксплуатации. Live route существует, но fail-closed и не может отправить order без PostgreSQL, Go/No-Go, runtime Bybit checks, approved persisted `RiskDecision`, DB-backed Go/No-Go evidence и явных operator flags.

Финальное production-live разрешение нельзя подтвердить внутри песочницы без реального Bybit-аккаунта, PostgreSQL и 2–4 недель paper/shadow evidence. Поэтому корректная live-ready логика проекта — блокировать live, пока внешние gates не подтверждены.

## Основные изменения текущей редакции

- Проведена дополнительная проверка по `prompts/total_project_check.txt`: hard invariants, CLI, risk/execution safety, ML leakage, same-bar ambiguity, frontend/source-of-truth, security и live gates.
- Добавлен `scripts/check_architecture.py`: проверяет обязательные слои проекта, отсутствие циклических app-зависимостей, отсутствие direct strategy -> execution/Bybit path, отсутствие target-equity tokens в risk/execution и отсутствие Bybit/secrets во frontend.
- `python main.py validate` теперь детерминированно запускает тот же validation pipeline через CLI без nested subprocess зависаний.
- `python main.py preflight --mode testnet|live` передает выбранный режим в preflight-скрипт и возвращает fail-closed JSON даже при недоступной PostgreSQL.
- Risk engine дополнительно fail-closed обрабатывает невалидные runtime specs (`tickSize`, `qtyStep`, `minQty`, `minNotional`, `maxLeverage`) и ошибки sizing без 500/bypass.
- ML pipeline получил leakage-checks: запрет future/target/label features, запрет случайного перемешивания временного ряда, проверку `feature_ts <= decision_ts`.
- Labels получили OHLC-вариант с консервативной обработкой same-bar TP/SL ambiguity.
- Manual action audit больше не падает на DB CHECK при попытке небезопасной команды: она сохраняется как `REJECTED_UNSAFE_ACTION` audit-marker без исполнимого маршрута.

- Усилен `run_live_preflight`: теперь live-gate проверяет не только `status=Trading`, но и положительные `tickSize`, `qtyStep`, `minQty`, `minNotional`, `maxLeverage` по каждому Bybit Linear instrument.
- Исправлен redaction: `apiSecret`, `BYBIT_API_KEY`, `X-BAPI-SIGN` и родственные ключи маскируются регистронезависимо.
- Исправлен config validator: запреты DCA/martingale/spot/inverse/options теперь регистронезависимы.
- Усилен sizing: reserve cash считается после conservative initial margin estimate, а не только после estimated costs.
- В risk engine добавлены daily/weekly remaining risk, portfolio absolute exposure и beta-adjusted exposure caps.
- Добавлен `docs/GO_NO_GO.md`.

- Добавлен корневой CLI `main.py`:
  - `python main.py` — запуск backend/dashboard;
  - `python main.py validate` — полная локальная проверка;
  - `python main.py preflight --mode testnet|live` — runtime gate без отправки ордеров.
- `scripts/run_backend.sh` переведен на единый CLI.
- README и документация переведены на русский язык.
- Dashboard-подписи переведены на русский без переноса бизнес-логики во frontend.
- Усилен POST `/api/risk/approve` для live/testnet-live: требуется operator key и `X-Idempotency-Key`; повтор с тем же ключом возвращает сохраненный результат, повтор с другим payload блокируется.
- Матрица трассируемости обновлена под текущую структуру проекта.

## Дополнительные исправления редакции 1.8

- Funding freshness выделен в отдельный fail-closed вход `MarketSnapshot.funding_fresh`; stale/missing funding теперь блокирует risk approval и переводит regime в `NO_TRADE`.
- `RiskEngine` дополнительно запрещает live-маршрут carry/funding/stat-arb alias-стратегий в Phase 0/1 даже если candidate ошибочно не помечен `shadow_only`.
- `RiskEngine` отдельно блокирует запрещенные продуктовые стратегии: martingale, DCA, spot/inverse/options, copy-trading и signal bot.
- Округление `qty` по `qtyStep` переведено на `Decimal`, чтобы бинарная ошибка float не могла округлить позицию вверх и увеличить риск.
- Добавлены regression-тесты на stale funding, forbidden/shadow-only strategies и Decimal floor-to-step.


## Дополнительные исправления редакции 1.9

- `/api/risk/approve` переведен в строгий write-endpoint: operator key и `X-Idempotency-Key` требуются всегда, включая локальный paper/demo режим.
- Конфигурационные запреты расширены на `copy_trading`, `signal_bot`, `portfolio_bot`; funding/stat-arb aliases в Phase 0/1 блокируются phase validator-ом.
- Manual config proposal/activation теперь принимаются только как risk-neutral/risk-reducing (`risk_change=same|decrease`) и отклоняют `risk_increase=true`.
- PostgreSQL view `latest_symbol_status` приведен к frontend-контракту: `status_effective`, `severity`, `reasons`, `trace_id`, `allowed_actions`, `updated_at`.
- Добавлены regression-тесты для product-scope запретов, manual action safety и DB/frontend status contract.

## Дополнительные исправления редакции 2.0

- Добавлена миграция `migrations/0003_hard_invariants.sql`, которая усиливает защиту от прямого SQL bypass: approved risk decision требует положительных sizing values, order qty/notional не может превышать approved sizing, signal/risk `feature_hash` должен совпадать, shadow/rejected signal не имеет live-route.
- Усилены DB constraints для `signals`, `positions` и `manual_request_log`: запрещены продуктовые стратегии, trade-candidate требует lineage/evidence, ACTIVE position не может быть flat/zero-qty, config activation/proposal не может повышать риск.
- `scripts/bootstrap_db.sh` теперь применяет все core-миграции автоматически и не применяет demo-seed без явного `CAS_SEED_DEMO_DATA=true`.
- Добавлены static regression-тесты `tests/test_migration_hard_invariants_static.py`; общий локальный набор вырос до 87 тестов.

## Что было реализовано ранее и сохранено

- `/api/execution/live-submit` с hard gates.
- `app/live/preflight.py` и `app/live/gate.py`.
- Runtime preflight fail-closed при live-флагах: проверяет DB, DB-backed Go/No-Go evidence, unresolved HIGH/CRITICAL, public/private Bybit checks и API-key trade permissions.
- `Settings` читает env при создании экземпляра, а не при импорте модуля.
- Startup guard блокирует live при demo mode, demo ML, unsafe keys, отсутствующем Go/No-Go и выключенном `CAS_ENABLE_LIVE_SUBMIT`.
- PostgreSQL repository поддерживает signal, ML verdict, risk decision, order intent, idempotent order reservation, order submitted/error, incidents, manual audit and Go/No-Go evidence.
- FastAPI state/incident routes используют PostgreSQL, если он доступен.
- Risk approval использует operator/idempotency guard; в live режиме дополнительно использует runtime Bybit specs/orderbook/funding/account data, сохраняет lineage в DB и блокируется без PostgreSQL.
- Bybit adapter поддерживает public/private runtime checks: server time, instruments-info, orderbook, funding, OI, wallet, positions, cancel-all and reduce-only exit helpers.
- Исправлена SQL migration ошибка с duplicate `trade_id`.
- `validate_project.py` включает compileall, pytest, strategy import check, architecture invariant check, migration invariant check and secret scan.

## Проверки

```bash
python main.py --help
python main.py validate
```

Ожидаемый результат локальной проверки:

```text
98 passed
OK: strategies have no direct execution/Bybit imports
OK: architecture invariants present
OK: migration static invariants present
OK: no obvious secrets
```

## Smoke endpoints

```text
/api/health             200 ok
/api/runtime/preflight  200 ok/blocked with reasons
/api/state/overview     200 ok
/api/risk/status        200 ok
/api/ml/health          200 ok
```

## Ограничения вне песочницы

Перед реальной торговлей оператор обязан поднять PostgreSQL, применить migrations, настроить Bybit keys, пройти `python main.py preflight --mode testnet`, накопить paper/shadow evidence, записать evidence в PostgreSQL, затем отдельно пройти `python main.py preflight --mode live` для production endpoint.


## Total project check — дополнительная редакция

- Усилен `RegimeClassifier`: нормативный priority order, safer mixed regime, immediate kill-switch, hysteresis и cooldown.
- Усилен `LimitedBreakoutStrategy`: SignalCandidate появляется только при structure/Donchian break, volume_z, ATR expansion, BTC alignment, OI sanity и funding sanity.
- Усилен `MicroGridStrategy`: hard stop, max_inventory=1, no_add_after_invalidation, ADX/funding gates; grid не становится DCA/martingale.
- Входные ордера `OrderRouter` теперь maker-only `PostOnly` по умолчанию; reduce-only market payload получает `closeOnTrigger` where applicable.
- Добавлены regression-тесты `tests/test_regime_classifier.py` и `tests/test_strategy_gates.py`.


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
98 passed

python main.py validate
compileall: PASS
pytest: 98 passed
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

## Редакция 4.0 — shadow/paper evidence hardening

- `CarryShadowScanner` и `StatArbShadowScanner` перестали быть пустыми заглушками: теперь они генерируют только `shadow_only=True` candidates для paper/shadow evidence.
- `StrategyOrchestrator(include_shadow=True)` используется только в paper pipeline; обычный live-orchestrator не добавляет shadow strategies.
- `PaperPipeline` сохраняет shadow decisions как `status=shadow_signal` и не передает их в `risk_engine`/`order_router`.
- Добавлены тесты `tests/test_shadow_scanners.py`: shadow candidates не имеют live route, risk gate возвращает `strategy_shadow_only`, order router возвращает `shadow_signal_has_no_live_route`.
- Локальная проверка: `python main.py validate` — 87 tests passed, static architecture checks PASS, migration checks PASS, secret scan PASS.

Статус остается безопасным: кодовая база `technical-live-ready/live-gated`, фактический live — `live-blocked` до PostgreSQL, Bybit runtime checks, paper/shadow evidence и Go/No-Go PASS.

---

## Редакция 5.0 — нормальный операторский модуль

Дата проверки: 2026-05-12.

### Что изменено

- Старый dashboard с сырым JSON заменен на полноценный операторский модуль: крупный статус, понятные карточки допуска, блокеры, план перехода к live, список символов, карточка деталей, безопасные действия и скрытая диагностика для разработчика.
- Добавлен backend endpoint `GET /api/operator/dashboard`, который формирует человекочитаемую модель интерфейса. Frontend не рассчитывает бизнес-статус и остается только визуальным слоем.
- Добавлены безопасные action-cards: `DISABLE_TRADING`, `CANCEL_OPEN_ENTRIES`, `FLATTEN_REDUCE`, `RESOLVE_INCIDENT`. Интерфейс требует operator key и причину; открытия сделки из UI нет.
- Добавлено руководство оператора в Markdown и DOCX: `docs/OPERATOR_MANUAL.md`, `docs/OPERATOR_MANUAL.docx`.
- Обновлены `README.md` и `docs/RUNBOOK.md` с упоминанием нового операторского модуля.
- Добавлены regression-тесты `tests/test_operator_module.py`.

### Измененные файлы

- `app/api/routes/operator.py`
- `app/main.py`
- `frontend/index.html`
- `frontend/css/styles.css`
- `frontend/js/api_client.js`
- `frontend/js/app.js`
- `tests/test_operator_module.py`
- `docs/OPERATOR_MANUAL.md`
- `docs/OPERATOR_MANUAL.docx`
- `docs/RUNBOOK.md`
- `README.md`
- `DELIVERY_REPORT.md`
- `TOTAL_PROJECT_CHECK_REPORT.md`

### Проверки редакции 5.0

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

### Итог редакции 5.0

Статус проекта остается безопасным: `test-ready`; `paper-ready` после подключения PostgreSQL/runtime data; `technical-live-ready` как live-gated кодовая база; фактический live остается `live-blocked` до PostgreSQL, Bybit runtime checks, paper/shadow evidence и Go/No-Go PASS.

## Редакция 5.0 — интерактивная контекстная справка

Добавлена встроенная справка оператора: правый клик по ключевому компоненту интерфейса открывает пункт «Вызвать справку», после выбора появляется диалог с конкретным объяснением выбранного блока, текущего статуса, действий оператора, критериев нормы и запретов. Справка покрывает верхний статус, панель допуска, блокеры, Phase 0 limits, план перехода к live, символы, детали символа, safe-actions, paper summary и техническую диагностику.

Проверки редакции 5.0:

- `python main.py validate` — PASS, 90 tests passed.
- `node --check frontend/js/context_help.js` — PASS.
- `node --check frontend/js/app.js` — PASS.
- `python main.py preflight --mode testnet` — ожидаемо blocked без внешней среды.
- `python main.py preflight --mode live` — ожидаемо blocked без внешней среды.

## Редакция: operator-command-center

Добавлен операторский запуск технических команд прямо из интерфейса без произвольного shell-доступа.

### Что изменено

- Добавлен backend allowlist-runner `app/services/operator_jobs.py`.
- Добавлены endpoints:
  - `GET /api/operator/commands`;
  - `POST /api/operator/commands/{command_id}/run`;
  - `GET /api/operator/jobs/{job_id}`.
- Добавлена Python-замена `./scripts/bootstrap_db.sh`: `python scripts/bootstrap_db.py`.
- `scripts/bootstrap_db.sh` оставлен только как совместимый wrapper на Python-реализацию.
- В операторский интерфейс добавлен блок **Операционный центр**.
- Frontend запускает только allowlist-команды backend: validate, testnet preflight, PostgreSQL migrations, live preflight.
- Команды требуют `OPERATOR_API_KEY`, причину запуска и `X-Idempotency-Key`.
- Запуск команд логируется в audit trail как `RUN_OPERATOR_COMMAND`, когда PostgreSQL доступен.
- Добавлена миграция `0004_operator_command_audit.sql`.
- Обновлены README, RUNBOOK и руководство оператора.

### Проверки

```text
python main.py validate
93 passed
compileall: PASS
architecture checks: PASS
migration checks: PASS
secret scan: PASS
```

Live-submit через этот блок не включается. `preflight_live` только проверяет gates и обязан оставаться `blocked`, пока нет PostgreSQL, Bybit runtime, paper/shadow evidence и Go/No-Go PASS.

## Редакция: operator-command-content-type-fix

Исправлена ошибка запуска операторских команд из браузера: при добавлении `x-api-key` frontend перезаписывал объект headers и терял `Content-Type: application/json`. FastAPI получал тело как строку и возвращал `422 Unprocessable Entity` с сообщением `Input should be a valid dictionary`.

### Что изменено

- `frontend/js/api_client.js` теперь сначала применяет `requestOptions`, а затем гарантированно добавляет `Content-Type: application/json` вместе с пользовательскими заголовками.
- `app/api/routes/operator_jobs.py` дополнительно умеет разобрать JSON-строку в теле запроса, чтобы старые вкладки/клиенты не получали непонятный 422.
- Добавлены regression-тесты на:
  - text/plain JSON body для `/api/operator/commands/{command_id}/run`;
  - сохранение `Content-Type` при кастомных headers во frontend API client.

### Проверки

```text
python main.py validate
95 passed
compileall: PASS
architecture checks: PASS
migration checks: PASS
secret scan: PASS

node --check frontend/js/api_client.js
node --check frontend/js/app.js
```

## Редакция 7.1 — исправление статусов операционных команд и preflight без migrations

Исправлены проблемы, выявленные при запуске команд из операторского экрана на Windows:

- `validate` больше не зависит от hardcoded `OPERATOR_API_KEY` в тестах. Тесты берут ключ из текущих runtime-настроек, поэтому пользовательский `.env` не ломает локальную проверку.
- `preflight_testnet` и `preflight_live` больше не падают traceback, если PostgreSQL доступен, но migrations еще не применены и таблиц `incidents` / `go_no_go_evidence` нет. Теперь возвращается понятный `status=blocked` с reasons:
  - `incidents_table_missing_or_migrations_not_applied`;
  - `go_no_go_tables_missing_or_migrations_not_applied`.
- Операционный центр больше не показывает зеленый `ok`, если CLI вывел `status=blocked`, traceback или pytest failures. Такие задания маркируются как `blocked` / `error`.
- Добавлены regression-тесты на оба сценария.

Проверка:

```bash
python main.py validate
# 97 passed
```


## Дополнительные исправления редакции 2.2

- Операторский экран уплотнен: панель допуска стала компактной, план и запуск команд объединены в один Операционный центр.
- На карточках плана добавлены кнопки запуска рядом с черными полями команд, где это безопасно и уместно.
- Убран визуальный дубль отдельного списка команд: backend allowlist остается, но UI запускает команды из плана.
- Исправлен regression для browser text/plain JSON body на `/api/operator/commands/{id}/run`.
- Исправлен тест startup guard, чтобы он не зависел от локального `OPERATOR_API_KEY` оператора.
- Testnet preflight отделен от live gate: больше не требует live-submit, Go/No-Go и 14+ дней paper evidence.
- Локальная проверка: `98 passed`, architecture checks, migration checks and secret scan PASS.

## Редакция: bybit private diagnostics

Исправлена непрозрачная блокировка `bybit_private_api_or_permissions_failed:RuntimeError` в testnet preflight.

Изменения:
- добавлен `BybitAPIError` с безопасными полями `ret_code`, `ret_msg`, `path`, `http_status`;
- private runtime checks разделены на auth/query-api, wallet-balance, positions и trade permissions;
- wallet-balance получает fallback `UNIFIED -> CONTRACT` для разных account mode;
- testnet/live preflight возвращает конкретные reasons: `bybit_private_api_auth_failed`, `bybit_wallet_balance_failed`, `bybit_positions_failed`, `bybit_api_key_trade_permission_not_verified`;
- оператор получает `data.bybit_private_errors` и `data.operator_private_api_hint` без вывода секретов;
- обновлены README, RUNBOOK и руководство оператора.

Проверка:

```text
python main.py validate
99 passed
compileall: PASS
architecture checks: PASS
migration checks: PASS
secret scan: PASS
```

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

## Редакция 8.3 — дополнительное закрытие обходов SignalCandidate/RiskDecision

Дата проверки: 2026-05-13.

### Исправления

- `RiskEngine` теперь требует полную lineage-связку `regime_id`, `feature_id`, `required_data` до approval.
- `OrderRouter` повторно проверяет lineage/evidence и не создает `OrderIntent`, если claimed approved sizing нарушает risk budget.
- `Repository.verify_live_risk_decision()` сверяет HTTP payload `RiskDecision.sizing` с persisted DB sizing до создания order reservation.
- Добавлены 3 regression-теста для новых hard-invariants.

### Проверки

```text
python main.py validate
compileall: PASS
pytest: 115 passed, 1 warning
strategy import check: PASS
architecture check: PASS
migration invariant check: PASS
secret scan: PASS
```

Testnet/live preflight в песочнице корректно возвращают `blocked` из-за отсутствующих внешних зависимостей: PostgreSQL, Bybit keys/runtime permissions и Go/No-Go evidence.


## Редакция 8.4 — frontend source-of-truth hardening для paper-резюме

- Paper endpoint теперь возвращает явный `status`/`reasons` по каждому решению, включая `risk_approved`/`risk_rejected`.
- Frontend больше не выводит paper-статус из `risk.approved` и не содержит ternary-логики `risk_approved/risk_rejected`.
- `scripts/check_architecture.py` получил static guard против такого локального вывода статуса.
- Добавлен regression-тест `test_paper_summary_does_not_derive_status_from_frontend_risk_approval`.
- Актуальная проверка: `python main.py validate` — `116 passed, 1 warning`; testnet/live preflight корректно остаются `blocked` без PostgreSQL, Bybit credentials/runtime и Go/No-Go evidence.

## Редакция 8.5 — защищенный testnet-dashboard и READONLY_API_KEY

Дата проверки: 2026-05-13.

### Исправления

- `python main.py serve --mode testnet` теперь запускает `APP_ENV=testnet`, а не принудительный `APP_ENV=local`; dashboard открывает PostgreSQL runtime repository и не показывает ложный `database_available=false` после успешного testnet preflight.
- Во frontend добавлен блок **Доступ к панели**: оператор вводит `READONLY_API_KEY`, ключ сохраняется только в `sessionStorage` текущей вкладки и автоматически отправляется как `x-api-key` для read-only endpoints.
- `api_client.js` автоматически добавляет `x-api-key` из sessionStorage для чтения dashboard, списка команд, статуса jobs и paper smoke; явно переданный `OPERATOR_API_KEY` для write endpoints имеет приоритет.
- `OPERATOR_API_KEY` можно временно использовать как read-key для polling результатов команды, но UI предупреждает, что предпочтителен отдельный `READONLY_API_KEY`.
- Ошибка `401 invalid_api_key` теперь объясняет оператору, что нужно указать `READONLY_API_KEY`/`OPERATOR_API_KEY`.

### Проверки

```text
python main.py validate
compileall: PASS
pytest: 118 passed, 1 warning
scripts/check_strategy_imports.py: PASS
scripts/check_architecture.py: PASS
scripts/check_migrations_static.py: PASS
scripts/secret_scan.py: PASS
```

### Операторский запуск testnet-dashboard

```powershell
python main.py serve --mode testnet --host 127.0.0.1 --port 8001
```

В браузере открыть `http://127.0.0.1:8001/`, вставить `READONLY_API_KEY` в блок **Доступ к панели**, нажать **Применить ключ чтения**, затем запускать `Testnet preflight` и `Paper один раз`. Live-флаги остаются выключенными.

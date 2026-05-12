# Отчет о поставке — total_project_check revision 1.7

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

## Что было реализовано ранее и сохранено

- `/api/execution/live-submit` с hard gates.
- `app/live/preflight.py` и `app/live/gate.py`.
- Runtime preflight fail-closed при live-флагах: проверяет DB, DB-backed Go/No-Go evidence, unresolved HIGH/CRITICAL, public/private Bybit checks и API-key trade permissions.
- `Settings` читает env при создании экземпляра, а не при импорте модуля.
- Startup guard блокирует live при demo mode, demo ML, unsafe keys, отсутствующем Go/No-Go и выключенном `CAS_ENABLE_LIVE_SUBMIT`.
- PostgreSQL repository поддерживает signal, ML verdict, risk decision, order intent, idempotent order reservation, order submitted/error, incidents, manual audit and Go/No-Go evidence.
- FastAPI state/incident routes используют PostgreSQL, если он доступен.
- Risk approval в live режиме использует runtime Bybit specs/orderbook/funding/account data, сохраняет lineage в DB и блокируется без PostgreSQL.
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
53 passed
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

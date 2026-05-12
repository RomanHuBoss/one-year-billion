# Отчет о поставке — live-gated revision 1.5

## Статус

Проект доработан до состояния **live-gated runtime** для локального запуска, testnet-проверок и подготовки к live-эксплуатации. Live route существует, но fail-closed и не может отправить order без PostgreSQL, Go/No-Go, runtime Bybit checks, approved persisted `RiskDecision`, DB-backed Go/No-Go evidence и явных operator flags.

Финальное production-live разрешение нельзя подтвердить внутри песочницы без реального Bybit-аккаунта, PostgreSQL и 2–4 недель paper/shadow evidence. Поэтому корректная live-ready логика проекта — блокировать live, пока внешние gates не подтверждены.

## Основные изменения текущей редакции

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
- `validate_project.py` включает compileall, pytest, strategy import check, migration invariant check and secret scan.

## Проверки

```bash
python main.py --help
python main.py validate
```

Ожидаемый результат локальной проверки:

```text
41 passed
OK: strategies have no direct execution/Bybit imports
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

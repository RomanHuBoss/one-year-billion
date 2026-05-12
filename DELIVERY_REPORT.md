# Delivery report — live-gated revision 1.4

## Статус

Проект доработан из локального safety-first прототипа в **live-gated runtime**: live route существует, но fail-closed и не может отправить order без PostgreSQL, Go/No-Go, runtime Bybit checks, approved persisted `RiskDecision`, DB-backed Go/No-Go evidence and explicit operator flags.

Важно: финальное production-live разрешение невозможно подтвердить внутри песочницы без реального Bybit-аккаунта, PostgreSQL и 2–4 недель paper/shadow evidence. Поэтому проект подготовлен так, чтобы **не пропускать live**, пока эти внешние gates не подтверждены.

## Основные изменения

- Добавлен `/api/execution/live-submit` с hard gates.
- Добавлен `app/live/preflight.py` and `app/live/gate.py`.
- Runtime preflight теперь fail-closed при live-флагах и проверяет DB, DB-backed Go/No-Go evidence, unresolved HIGH/CRITICAL, public/private Bybit checks and API-key trade permissions.
- `Settings` теперь читает env при создании экземпляра, а не при импорте модуля.
- Startup guard усилен: live запрещен с demo mode, demo ML, unsafe keys, отсутствующим Go/No-Go и выключенным `CAS_ENABLE_LIVE_SUBMIT`.
- PostgreSQL repository расширен: persist signal, ML verdict, risk decision, order intent, idempotent order reservation, order submitted/error, incidents, manual audit and Go/No-Go evidence.
- FastAPI state/incident routes используют PostgreSQL, если он доступен.
- Risk approval route в live режиме использует runtime Bybit specs/orderbook/funding/account data, сохраняет lineage в DB и блокируется без PostgreSQL.
- Bybit adapter расширен public/private runtime checks: server time, instruments-info, orderbook, funding, OI, wallet, positions, cancel-all and reduce-only exit helpers.
- Добавлен market data normalization module for Bybit runtime specs and orderbook snapshots.
- Исправлена SQL migration ошибка с duplicate `trade_id`.
- Добавлен migration static invariant checker.
- `validate_project.py` теперь включает compileall, pytest, strategy import check, migration invariant check and secret scan.
- Добавлены тесты live gates, live-submit locked route, persistent idempotency, ambiguous submit failure, Go/No-Go evidence gate, market data normalization.

## Проверки

```bash
python scripts/validate_project.py
# 40 passed
# OK: strategies have no direct execution/Bybit imports
# OK: migration static invariants present
# OK: no obvious secrets
```

Smoke endpoints:

```text
/api/health             200 ok
/api/runtime/preflight  200 ok
/api/state/overview     200 ok
/api/risk/status        200 ok
/api/ml/health          200 ok
```

## Live limitations outside sandbox

Перед реальной торговлей оператор обязан поднять PostgreSQL, применить migrations, настроить Bybit keys, пройти `scripts/live_preflight.py`, накопить paper/shadow evidence, записать evidence в PostgreSQL and set Go/No-Go approval variables.

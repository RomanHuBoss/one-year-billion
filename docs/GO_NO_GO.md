# Go/No-Go перед live

Этот документ фиксирует эксплуатационный gate. Он не является разрешением на торговлю сам по себе: live остается заблокированным, пока `python main.py preflight --mode live` не вернет `status=ok`, а PostgreSQL не содержит подтвержденные evidence-записи.

## Обязательные условия PASS

1. `python main.py validate` прошел без ошибок.
2. PostgreSQL поднят, миграции применены, `DATABASE_URL` указывает на рабочую БД.
3. Runtime Bybit checks прошли: public API, private API, права ключа, `category=linear`, `status=Trading`, положительные `tickSize`, `qtyStep`, `minQty`, `minNotional`, `maxLeverage` по каждому символу Phase 0.
4. В БД нет открытых CRITICAL/HIGH incidents.
5. Есть не менее 14 дней Phase 0 paper/shadow evidence с `reconciliation_pass_rate=1.0` и `unresolved_incidents=0`.
6. Есть evidence `RECONCILIATION=PASS`, `SECURITY=PASS`, `CI=PASS`, `GO_NO_GO=PASS` с текущим `config_hash`.
7. Live-флаги включены явно: `TRADING_ENABLED=true`, `CAS_ENABLE_LIVE_SUBMIT=true`, `BYBIT_LIVE_CONFIRM=true`, `BYBIT_TESTNET=false`.
8. Demo-режимы выключены: `CAS_DEMO_MODE=false`, `CAS_ALLOW_DEMO_ML=false`.
9. `OPERATOR_API_KEY` и `READONLY_API_KEY` заданы как разные длинные случайные значения.
10. Оператор подтвердил, что API-ключи Bybit хранятся только server-side и не попали во frontend, git, логи или screenshots.

## Команды проверки

```bash
python main.py validate
python main.py preflight --mode testnet
python main.py preflight --mode live
```

Evidence записывается только после реальной проверки:

```bash
python scripts/record_go_no_go_evidence.py --type PHASE0_PAPER --status PASS --started-at 2026-05-01T00:00:00Z --ended-at 2026-05-15T00:00:00Z --metrics-json '{"reconciliation_pass_rate":1.0,"unresolved_incidents":0}'
python scripts/record_go_no_go_evidence.py --type RECONCILIATION --status PASS --metrics-json '{"pass_rate":1.0}'
python scripts/record_go_no_go_evidence.py --type SECURITY --status PASS --metrics-json '{"secret_scan":"PASS"}'
python scripts/record_go_no_go_evidence.py --type CI --status PASS --metrics-json '{"tests":108}'
python scripts/record_go_no_go_evidence.py --type GO_NO_GO --status PASS --approved-by "<product-owner>"
```

## Автоматический FAIL

- Любой unresolved CRITICAL/HIGH incident.
- Любой stale instruments/account/orderbook/funding input перед risk approval.
- Отсутствие approved non-expired `risk_decision_id` в PostgreSQL.
- Попытка ACTIVE без `protection_state=VALID` и `reconciliation_status=PASS`.
- Runtime instruments без положительных `tickSize`, `qtyStep`, `minQty`, `minNotional`, `maxLeverage`.
- Любой live-route для carry/stat-arb в Phase 0/1.
- Любой manual action, который может открыть новую позицию, увеличить risk, изменить leverage или обойти risk engine.

## Итоговый статус архива

Код находится в состоянии **technical-live-ready / live-gated**. Он готов к локальному запуску, testnet-preflight и paper/shadow. Реальный live остается **live-blocked**, пока внешняя среда и доказательства выше не подтверждены.

## Последняя локальная проверка архива

Локальная проверка последней редакции: `python main.py validate` — PASS, `112 passed`. Testnet/live preflight в песочнице корректно возвращают `blocked`, потому что нет внешней PostgreSQL, Bybit API keys и Go/No-Go evidence.

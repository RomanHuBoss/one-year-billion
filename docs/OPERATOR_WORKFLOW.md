# Операторский мастер запуска

Новая операторская панель устроена как мастер запуска, а не как набор разрозненных карточек и консольных подсказок.

## Принцип работы

- Оператор открывает `python main.py serve --mode testnet --port 8001` и работает через браузер.
- Все ключевые вехи отображаются одним списком: БД, validate/CI, testnet preflight, paper/shadow, security, reconciliation, Go/No-Go, live preflight.
- Крупный шаг считается завершенным только если завершены его обязательные подшаги.
- Следующий шаг закрыт, пока предыдущий gate не завершен.
- Frontend не вычисляет readiness сам: он получает `/api/operator/workflow` от backend и только отображает результат.
- Запуск действий идет через `/api/operator/workflow/actions/{action_id}` с `OPERATOR_API_KEY`, idempotency key и audit-причиной.

## Что больше не нужно делать руками

Штатный операторский сценарий больше не требует вводить команды вида:

```powershell
python scripts/record_go_no_go_evidence.py ...
python main.py validate
python main.py preflight --mode testnet
python main.py preflight --mode live
```

Эти действия доступны из панели. Терминал остается резервным способом диагностики и аварийного восстановления.

## Ключевые действия в UI

1. **Применить migrations** — запускает allowlist-команду `bootstrap_db`.
2. **Запустить validate** — запускает `python main.py validate` через backend job-runner.
3. **Записать CI PASS** — записывает evidence в PostgreSQL после успешной проверки.
4. **Запустить testnet preflight** — проверяет Bybit testnet/runtime gates.
5. **Начать paper/shadow период** — записывает `PHASE0_PAPER=PENDING` и включает счетчик 14 дней.
6. **Запустить paper один раз** — выполняет paper pipeline без live-order.
7. **Записать SECURITY PASS** — фиксирует security evidence после проверок.
8. **Записать RECONCILIATION PASS** — фиксирует сверку local/exchange state.
9. **Записать GO/NO-GO PASS** — доступно только после предыдущих gate и требует `approved_by`.
10. **Запустить live preflight** — проверка допуска; сама по себе не включает live-submit.

## Safety-модель

Панель не является торговым терминалом. Она не открывает сделки, не хранит Bybit keys, не считает размер позиции, не меняет плечо и не обходит risk engine.

Live остается невозможным до полного прохождения Go/No-Go, evidence, reconciliation и live preflight. Hard-инварианты остаются на backend/API/DB уровне.

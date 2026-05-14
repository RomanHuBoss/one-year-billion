# Операторский runbook

## Обычный локальный запуск

```bash
source .venv/bin/activate
cp .env.example .env
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/cas2026
python scripts/bootstrap_db.py
python main.py
```

Dashboard / операторский модуль: `http://127.0.0.1:8000/`. В блоке **Операционный центр** можно запускать validate, preflight и `python scripts/bootstrap_db.py` прямо из браузера через backend allowlist-runner.

Откройте операторский модуль и сначала смотрите блоки **Текущее состояние**, **Что мешает запуску** и **План перехода от теста к live**. Сырой JSON спрятан в диагностике и нужен только для разработчика.


## Операционный центр в браузере

Основные проверки можно выполнять без терминала:

1. Откройте `/`.
2. Найдите блок **Операционный центр**.
3. Введите `OPERATOR_API_KEY`.
4. Введите причину запуска.
5. Нажмите нужную команду.

Доступны только allowlist-команды: validate, testnet preflight, PostgreSQL bootstrap через `python scripts/bootstrap_db.py`, live preflight. Произвольные команды, shell, psql и отправка live-ордера из этого блока невозможны.

## Бумажный контур

Откройте `/` и нажмите **Запустить paper один раз** или вызовите endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/run-once
```

## Runtime/live preflight

Live-submit отключен по умолчанию. Перед любой попыткой testnet/live выполните:

```bash
python main.py preflight --mode testnet
```

Для production-live:

```bash
python main.py preflight --mode live
```

Успешный результат должен содержать:

```json
{"status": "ok"}
```

`blocked` — нормальное состояние до тех пор, пока отсутствуют PostgreSQL, Bybit credentials, runtime specs, private account access, trade permission API key, DB-recorded paper/reconciliation/security/CI/Go-No-Go evidence и operator approval.

## Минимальное live/testnet окружение

```bash
export APP_ENV=prod
export DATABASE_URL=postgresql://...
export OPERATOR_API_KEY=<long-random-operator-key>
export READONLY_API_KEY=<different-long-random-readonly-key>
export BYBIT_TESTNET=true                # сначала testnet
export BYBIT_API_KEY=<server-side-only>
# BYBIT_API_SECRET задайте в shell/secret store; не фиксируйте значение в документации.
export BYBIT_LIVE_CONFIRM=true
export TRADING_ENABLED=true
export CAS_ENABLE_LIVE_SUBMIT=true
export CAS_REQUIRE_DB_FOR_LIVE=true
export CAS_REQUIRE_LIVE_PREFLIGHT=true
export CAS_REQUIRE_GO_NOGO_FOR_LIVE=true
export CAS_GO_NOGO_PASS=true
export CAS_LIVE_APPROVED_BY=<product-owner>
export CAS_ALLOW_DEMO_ML=false
export CAS_DEMO_MODE=false
```

Production endpoint (`BYBIT_TESTNET=false`) включается только после PASS на testnet и после обязательного DB-recorded paper/shadow evidence.

## Контракт live-submit

Live order route: `POST /api/execution/live-submit`.

Он заблокирован следующими условиями:

1. `CAS_ENABLE_LIVE_SUBMIT=true`;
2. `TRADING_ENABLED=true` и `BYBIT_LIVE_CONFIRM=true`;
3. server-side Bybit credentials;
4. PostgreSQL availability;
5. no unresolved HIGH/CRITICAL incidents;
6. env Go/No-Go approval плюс DB-recorded evidence;
7. runtime Bybit public/private/permission checks;
8. persisted approved non-expired `RiskDecision` in DB;
9. deterministic `orderLinkId` и persistent idempotency key.

HTTP ack от Bybit не считается fill. Следующий обязательный этап — private WS или REST reconciliation, затем verification защиты позиции.

## Risk approval

POST `/api/risk/approve` является write-endpoint и всегда требует:

- `x-api-key: <OPERATOR_API_KEY>`;
- `X-Idempotency-Key: <unique-key>`.

Readonly/local read-доступ не может создавать `RiskDecision`; повтор с тем же idempotency key возвращает сохраненный результат, а повтор с другим payload блокируется.

## Аварийные действия

Разрешены только действия, снижающие риск:

- `DISABLE_TRADING`
- `CANCEL_OPEN_ENTRIES`
- `FLATTEN_REDUCE`
- `RESOLVE_INCIDENT`
- `PROPOSE_CONFIG`
- `ACTIVATE_CONFIG`

Endpoint принудительного открытия сделки отсутствует.

## Проверка

```bash
python main.py validate
python main.py preflight --mode testnet
```

`validate` должен проходить локально. `preflight --mode live` должен проходить только в реальной runtime-среде с доказательствами.

## Запись Go/No-Go evidence

Используйте эти команды только после реального получения evidence. Live gate читает строки из PostgreSQL; env-флагов недостаточно.

```bash
python scripts/record_go_no_go_evidence.py --type PHASE0_PAPER --status PASS --started-at 2026-05-01T00:00:00Z --ended-at 2026-05-15T00:00:00Z --metrics-json '{"reconciliation_pass_rate":1.0,"unresolved_incidents":0}'
python scripts/record_go_no_go_evidence.py --type RECONCILIATION --status PASS --metrics-json '{"pass_rate":1.0}'
python scripts/record_go_no_go_evidence.py --type SECURITY --status PASS --metrics-json '{"secret_scan":"PASS"}'
python scripts/record_go_no_go_evidence.py --type CI --status PASS --metrics-json '{"tests":133}'
python scripts/record_go_no_go_evidence.py --type GO_NO_GO --status PASS --approved-by <product-owner>
```

Если live-submit получил неоднозначный REST failure после резервирования order, order переводится в `ERROR_RECONCILIATION_REQUIRED`. Не повторяйте submit с новым idempotency key, пока reconciliation не подтвердит состояние биржи.

## Диагностика Операционного центра

Если команда вернула traceback, это не должно отображаться как `ok`. Актуальная логика статусов такая:

- `ok` — команда реально завершилась успешно;
- `blocked` — проверка штатно заблокирована fail-closed, например нет evidence или PostgreSQL не готов;
- `error` — traceback, pytest failure или ошибка исполнения;
- `timeout` — команда не завершилась за допустимое время.

Если PostgreSQL уже запущен, но preflight пишет, что таблица `incidents` или `go_no_go_evidence` отсутствует, сначала выполните из интерфейса **PostgreSQL: применить migrations**. Это нормальный первый шаг, а не повод включать live вручную.


## Операторский экран 2.2

1. Откройте `http://127.0.0.1:8000/`.
2. В блоке **Операционный центр: план и запуск** укажите `OPERATOR_API_KEY` и причину.
3. Запускайте `validate`, `testnet preflight`, `PostgreSQL migrations` и `live preflight` кнопками прямо на карточках плана.
4. `testnet preflight` не требует live-submit и Go/No-Go. Если он blocked, исправляйте причины testnet/DB/runtime.
5. `live preflight` до full PASS обязан оставаться blocked. Это нормальное fail-closed состояние.

## Разбор блокировки `bybit_private_api_*` в testnet

Симптом: public API reachable, runtime specs verified, но private API или permissions false.

Порядок действий:

1. Проверить `BYBIT_TESTNET=true`.
2. Проверить, что ключ создан в testnet Bybit, а не live Bybit.
3. Скопировать `ret_code`, `ret_msg`, `path` из `data.bybit_private_errors`.
4. Проверить IP whitelist ключа.
5. Проверить permissions: Linear/Contract/Derivatives, Order/Trade, Positions/Wallet.
6. Перезапустить backend после правки `.env`.
7. Повторить Testnet preflight.

До исчезновения этих причин testnet readiness считается BLOCKED. Это правильное fail-closed состояние.

## Разбор `API 401: invalid_api_key`

1. Если сообщение пришло из браузера как `Ошибка API 401: invalid_api_key`, проверять нужно backend-ключ: `OPERATOR_API_KEY`/`READONLY_API_KEY`. Введите его в поле **API-доступ**. Не вводите туда ключ Bybit.
2. Если отказ появляется при write-action или запуске команды, используйте именно `OPERATOR_API_KEY`; `READONLY_API_KEY` должен давать только чтение.
3. Если отказ находится внутри `bybit_private_api_auth_failed`, проверяйте Bybit testnet/live endpoint, ключ, secret, IP whitelist и Linear/Contract/Derivatives permissions.
4. После правки `.env` перезапустите backend: `python main.py serve --mode testnet`.


## Операторский мастер запуска

Операторская панель переработана в пошаговый мастер. Все ключевые вехи доступны из frontend: PostgreSQL/migrations, validate/CI evidence, testnet preflight, старт и контроль 14-дневного Phase 0 paper/shadow, security evidence, reconciliation evidence, подписанный Go/No-Go и live preflight. Каждый следующий gate закрыт, пока обязательные подшаги предыдущего gate не завершены. Терминальные команды остаются резервным способом диагностики; штатная работа оператора выполняется через браузер.

Подробности по операторскому процессу включены в `docs/OPERATOR_MANUAL.docx` и `docs/RUNBOOK.md`.

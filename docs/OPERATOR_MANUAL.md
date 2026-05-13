# Руководство оператора

## Назначение

Операторский модуль создан для безопасной работы с Crypto Acceleration System 2026. Он не является торговым терминалом для ручного открытия сделок. Его задача - показать, можно ли тестировать систему, почему live сейчас заблокирован, какие проверки еще нужны и какие безопасные действия доступны оператору.

## Главное правило

Если интерфейс показывает `Live заблокирован`, это не ошибка. До полного Go/No-Go PASS система обязана блокировать live. Оператор не должен искать обходной путь.

## Как открыть модуль

```bash
python main.py
```

Затем открыть в браузере:

```text
http://127.0.0.1:8000/
```

## Что смотреть первым

1. **Текущее состояние** - крупный верхний блок. Он отвечает на вопрос: можно ли продолжать и что делать следующим шагом.
2. **Панель допуска** - короткие карточки по торговле, БД, risk engine, live gate, фазе и ML.
3. **Что мешает запуску** - список причин блокировки. Исправлять сверху вниз.
4. **Операционный центр** - запуск разрешенных backend-команд без терминала: validate, preflight и PostgreSQL migrations.
5. **План перехода от теста к live** - последовательность проверок.
6. **Символы** - понятный статус BTCUSDT, ETHUSDT, SOLUSDT.
7. **Безопасные действия оператора** - только disable/cancel/flatten/resolve. Открытия сделки из интерфейса нет.

## Безопасные стартовые настройки Phase 0

- `TRADING_ENABLED=false`
- `CAS_ENABLE_LIVE_SUBMIT=false`
- `BYBIT_LIVE_CONFIRM=false`
- `BYBIT_TESTNET=true`
- `CAS_REQUIRE_DB_FOR_LIVE=true`
- `CAS_REQUIRE_LIVE_PREFLIGHT=true`
- `CAS_REQUIRE_GO_NOGO_FOR_LIVE=true`
- `CAS_GO_NOGO_PASS=false`
- `CAS_DEMO_MODE=false`
- `CAS_ALLOW_DEMO_ML=false`

Phase 0: только BTCUSDT, ETHUSDT, SOLUSDT. Риск по умолчанию 1%, абсолютный максимум 1.5%, эффективное плечо по умолчанию не выше 3x.

## Проверки перед testnet

Рекомендуемый путь для оператора — запускать проверки из блока **Операционный центр**. Терминальные команды остаются резервным вариантом:

```bash
python main.py validate
python main.py preflight --mode testnet
```

`validate` должен пройти без ошибок. `preflight --mode testnet` может вернуть `blocked`, если нет ключей, БД или runtime-доступа. Это нормально: исправьте причины из интерфейса и повторите.


## Операционный центр: команды прямо из интерфейса

Теперь основные команды можно запускать из браузера без ручного терминала. Это сделано безопасно: браузер не получает shell-доступ и не может отправить произвольную команду. Он вызывает backend endpoint, а backend запускает только allowlist-команды Python.

Доступные команды:

| Команда в интерфейсе | Что делает | Безопасность |
|---|---|---|
| Локальная проверка проекта | Запускает `python main.py validate` | Не отправляет ордера |
| Testnet preflight | Запускает `python main.py preflight --mode testnet` | Проверка без реальных денег |
| PostgreSQL: применить migrations | Запускает `python scripts/bootstrap_db.py` | Python-замена `./scripts/bootstrap_db.sh`, без shell/psql |
| Live preflight | Запускает `python main.py preflight --mode live` | Только проверяет gates; live-submit не включает |

Как запускать:

1. Откройте блок **Операционный центр**.
2. Введите `OPERATOR_API_KEY`.
3. Введите причину запуска: например, «первичная настройка PostgreSQL» или «проверка перед testnet».
4. Нажмите нужную команду.
5. Дождитесь статуса job и прочитайте `stdout/stderr`.

Важное ограничение: `Live preflight` не является кнопкой «начать торговать». Это только проверка. Даже при `status=ok` каждый live-order все равно требует approved `RiskDecision`, idempotency, DB constraints, reconciliation и protection.

## Paper/shadow

В интерфейсе нажать **Paper один раз** для smoke-проверки конвейера. Для допуска к live нужен не одиночный запуск, а 14+ дней Phase 0 paper/shadow evidence с reconciliation PASS и без unresolved incidents.

## Когда можно переходить к реальной торговле

Только когда выполнено все:

1. `python main.py validate` - PASS.
2. PostgreSQL поднят, миграции применены.
3. `python main.py preflight --mode testnet` - PASS.
4. Накоплено не менее 14 дней Phase 0 paper/shadow evidence.
5. Нет unresolved CRITICAL/HIGH incidents.
6. Есть evidence `RECONCILIATION=PASS`, `SECURITY=PASS`, `CI=PASS`.
7. Есть подписанный `GO_NO_GO=PASS`.
8. `python main.py preflight --mode live` - PASS.
9. API-ключи Bybit хранятся только server-side.
10. Оператор понимает, что HTTP ack от Bybit не является fill; ACTIVE допустим только после reconciliation PASS и protection_state=VALID.

## Что запрещено

- Открывать сделку вручную в обход risk engine.
- Повторять submit с новым idempotency key после timeout.
- Увеличивать риск из-за просадки или желания быстрее выйти к цели.
- Включать carry/stat-arb live в Phase 0/1.
- Хранить ключи Bybit во frontend или отправлять их в браузер.
- Считать `blocked` ошибкой интерфейса без анализа причин.

## Аварийные действия

Разрешены только действия, снижающие риск:

- `DISABLE_TRADING` - выключить новые входы.
- `CANCEL_OPEN_ENTRIES` - отменить открытые входные заявки.
- `FLATTEN_REDUCE` - уменьшить или закрыть риск через reduce-only.
- `RESOLVE_INCIDENT` - закрыть инцидент только после проверки.

Каждое действие требует `OPERATOR_API_KEY` и понятную причину.

## Интерактивная справка прямо в интерфейсе

В новой версии операторского модуля у каждого ключевого блока есть контекстная справка.

Как пользоваться:

1. Наведите мышь на непонятный блок: карточку допуска, блокер, шаг плана, символ, safe-action, результат paper или диагностику.
2. Нажмите правую кнопку мыши.
3. Выберите пункт **«Вызвать справку»**.
4. Прочитайте диалог: там указано, что означает блок, что делать оператору, когда состояние считается нормой и чего нельзя делать.

Примеры:

- Правая кнопка по карточке **Live gate** объяснит, почему live закрыт и какие gates нужно пройти.
- Правая кнопка по символу **BTCUSDT** объяснит его `status_effective`, причины вроде `stale_market`, разрешенные действия и Trace ID.
- Правая кнопка по шагу **PostgreSQL и миграции** покажет команду и критерий PASS.
- Правая кнопка по действию **Снизить / закрыть риск** объяснит, когда его можно применять и почему оно не является торговой кнопкой.

Кнопка **«Справка»** в верхней панели открывает общую справку по экрану.

## Что делать с результатами команд

В Операционном центре смотрите не только на текст stdout/stderr, но и на статус карточки:

| Статус | Что означает | Что делать |
|---|---|---|
| `ok` | Команда прошла | Переходите к следующему шагу плана |
| `blocked` | Система безопасно не дала пройти дальше | Читайте `reasons`, исправляйте причину и повторяйте |
| `error` | Ошибка исполнения, traceback или упавший тест | Остановитесь, исправьте код/настройки, live запрещен |
| `timeout` | Команда зависла или не уложилась во время | Проверьте PostgreSQL, сеть, зависимости и повторите |

Если preflight показывает `incidents_table_missing_or_migrations_not_applied` или `go_no_go_tables_missing_or_migrations_not_applied`, нажмите **PostgreSQL: применить migrations**. До этого live-проверка не обязана проходить.

## Обновление интерфейса: меньше дублей, команды прямо в плане

Новая компоновка экрана устроена так:

1. **Главный статус** — один верхний ответ: что происходит и что делать сейчас.
2. **Панель допуска** — короткие компактные индикаторы, а не отдельный большой отчет.
3. **Операционный центр: план и запуск** — единый блок вместо двух дублирующих разделов. Команда показана в черном поле, а справа от нее есть кнопка запуска `▶`. Если кнопки нет, значит шаг требует ручной записи evidence или длительного paper/shadow периода.
4. **Что мешает запуску** и **Настройки Phase 0** — рядом, чтобы не тратить вертикальное место.
5. **Символы** и **Детали символа** — рядом: выбрали пару слева, расшифровку сразу видите справа.

### Как запускать команду из карточки плана

1. В блоке **Операционный центр: план и запуск** введите `OPERATOR_API_KEY`.
2. Введите причину запуска. Пример: `проверка после исправления тестов`, `применение миграций PostgreSQL`, `testnet preflight после настройки ключей`.
3. На нужной карточке нажмите **Запустить** или кнопку `▶` рядом с черным полем команды.
4. Дождитесь результата в блоке под планом.
5. Если статус `blocked`, смотрите `reasons`. Если статус `error`, исправляйте traceback/pytest failure; live запрещен.

### Testnet preflight больше не требует live Go/No-Go

`python main.py preflight --mode testnet` теперь проверяет именно testnet readiness. Он не должен требовать `CAS_ENABLE_LIVE_SUBMIT`, live Go/No-Go и 14 дней paper evidence. Если testnet preflight заблокирован, причины должны быть уровня: нет PostgreSQL, нет testnet Bybit credentials, не выбран testnet endpoint, не применены migrations или есть unresolved incidents.

`python main.py preflight --mode live` остается строгим live gate и обязан требовать DB, Bybit runtime, paper/shadow evidence, security/CI/reconciliation evidence, signed Go/No-Go и отсутствие unresolved CRITICAL/HIGH.

## Testnet preflight: public OK, private API заблокирован

Если `python main.py preflight --mode testnet` показывает примерно такое:

```json
{
  "status": "blocked",
  "reasons": ["bybit_private_api_auth_failed:..."],
  "checks": {
    "bybit_public_api_reachable": true,
    "runtime_instrument_specs_verified": true,
    "bybit_private_api_verified": false,
    "bybit_api_key_trade_permission_verified": false
  }
}
```

это значит: публичная часть Bybit доступна, спецификации BTC/ETH/SOL прочитаны, но private API не подтвердил ключи или permissions. Это не ошибка frontend и не причина включать live вручную.

Что делать оператору:

1. Убедиться, что `BYBIT_TESTNET=true`.
2. Проверить, что `BYBIT_API_KEY` и `BYBIT_API_SECRET` созданы именно в Bybit testnet, а не в live-кабинете.
3. Проверить, что в `.env` нет лишних пробелов, кавычек и переносов строк в ключах.
4. Проверить IP whitelist ключа Bybit: IP текущего ПК/VPS должен быть разрешен.
5. Проверить права API-ключа: для testnet runtime нужны Linear/Contract/Derivatives права на чтение wallet/positions и trade/order permission для дальнейших testnet-сценариев.
6. Перезапустить backend после изменения `.env`.
7. Повторить `Testnet preflight` из интерфейса.

Актуальная версия preflight показывает не общий `RuntimeError`, а конкретные причины: `bybit_private_api_auth_failed`, `bybit_wallet_balance_failed`, `bybit_positions_failed`, `bybit_api_key_trade_permission_not_verified`, а также безопасную диагностику `ret_code`, `ret_msg`, `path` без вывода секретов.

## Ошибка `API 401: invalid_api_key`

Если ошибка показана в браузере при открытии dashboard, обновлении команд или запуске safe-action, backend не принял ключ доступа оператора. Это не Bybit API key. Введите в верхней панели **API-доступ** значение `OPERATOR_API_KEY` или `READONLY_API_KEY` из `.env` без пробелов, кавычек и переносов строк. Для запуска команд и безопасных действий подходит только `OPERATOR_API_KEY`.

Если похожая ошибка находится внутри результата testnet preflight как `bybit_private_api_auth_failed`, значит публичный Bybit может быть доступен, но private API не подтвердил ключи. Тогда проверьте testnet/live кабинет, secret, IP whitelist и permissions, затем перезапустите backend.

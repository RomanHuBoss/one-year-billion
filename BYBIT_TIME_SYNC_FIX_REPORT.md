# Исправление Bybit retCode=10002 timestamp/recv_window

## Диагноз

Bybit private API вернул `retCode=10002`:

```text
invalid request, please check your server timestamp or recv_window param
```

Это не ошибка API-ключа. В присланном логе `req_timestamp` был примерно на 1.38 секунды впереди `server_timestamp`. Для Bybit V5 это может быть отклонено, потому что timestamp private request должен попадать в окно:

```text
server_time - recv_window <= timestamp < server_time + 1000
```

Увеличение `recv_window` помогает только при запаздывающем запросе, но не решает случай, когда локальные часы уходят вперед более чем на 1000 мс.

## Что изменено

- `BybitAdapter` теперь синхронизирует private подписи с Bybit `/v5/market/time`.
- Для private headers используется `local_time + server_time_offset - safety_margin`.
- Добавлены настройки:
  - `BYBIT_RECV_WINDOW_MS=8000`
  - `BYBIT_TIME_SYNC_TTL_SEC=60`
  - `BYBIT_TIME_SAFETY_MARGIN_MS=250`
- `retCode=10002` нормализуется как `bybit_timestamp_window_error`, а не как generic `bybit_request_rejected`.
- Preflight возвращает оператору `bybit_time_sync` и понятный hint: это проблема времени/recv_window, а не испорченный ключ.
- Frontend показывает отдельный блок `Что делать оператору` для таких ошибок, не заставляя разбирать сырой stdout.

## Что осталось безопасным

- Live-submit не включается.
- Private API failures остаются fail-closed: `testnet preflight = blocked`, пока Bybit не подтвердит private checks.
- Секреты и API-key не попадают в diagnostics/UI/tests.

## Проверка

```text
python main.py validate
pytest: 133 passed, 1 warning
check_strategy_imports: OK
check_architecture: OK
check_migrations_static: OK
secret_scan: OK
```

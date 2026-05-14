# Исправление workflow: шаг PostgreSQL не переходил в PASS после migrations

## Причина

Операторская панель запускалась командой `python main.py serve --mode testnet`, где backend намеренно работал в безопасном local/testnet режиме и не открывал PostgreSQL на startup. Кнопка «Применить migrations» запускала `scripts/bootstrap_db.py` в отдельном allowlist subprocess и успешно применяла SQL migrations, но состояние работающего FastAPI-процесса (`app.state.db_available`, `app.state.repository`) после этого не обновлялось.

Из-за этого backend workflow видел:

```json
"jobs": [{"command_id":"bootstrap_db","status":"ok"}],
"database_available": false,
"repository_available": false
```

и оставлял шаг «База данных и миграции» в `todo`.

## Исправление

Добавлен ленивый backend refresh PostgreSQL-состояния:

- `app/db/availability.py`;
- `ensure_database_ready(app)`;
- проверка не только `SELECT 1`, но и обязательных таблиц operator/risk/evidence слоя;
- workflow теперь различает:
  - `connection_ok`: PostgreSQL доступен;
  - `schema_ready`: применены migrations с hard constraints/audit/evidence;
- `GET /api/operator/workflow` сам перепроверяет БД после bootstrap job и переводит шаг DB в `ok` без перезапуска сервера;
- legacy dashboard/runtime diagnostics также показывают `database_schema_ready`, `database_missing_tables`, `database_error`.

## Проверки

```text
python main.py validate
pytest: 129 passed, 1 warning
check_strategy_imports: OK
check_architecture: OK
check_migrations_static: OK
secret_scan: OK
```

## Ожидаемое поведение после фикса

После нажатия «Применить migrations» и завершения job со статусом `ok` следующий refresh workflow должен показать:

```json
"database_available": true,
"database_schema_ready": true,
"steps[0].status": "ok",
"steps[0].blocks_next": false,
"current_step_id": "validate"
```

Если PostgreSQL доступен, но migrations не применены, шаг остается `todo`, а `database_missing_tables` показывает, каких таблиц не хватает.

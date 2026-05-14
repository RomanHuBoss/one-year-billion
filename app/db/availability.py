from __future__ import annotations

from typing import Any

from app.db.connection import Database
from app.db.repository import Repository

# Минимальный набор таблиц, без которых операторский workflow не имеет права
# считать шаг PostgreSQL завершенным. SELECT 1 показывает только доступность
# сервера, но не доказывает наличие hard constraints/audit/evidence слоя.
REQUIRED_OPERATOR_TABLES = [
    'go_no_go_evidence',
    'manual_request_log',
    'incidents',
    'risk_decisions',
    'orders',
    'positions',
]


def _tables_ready(db: Database) -> tuple[bool, list[str]]:
    rows = db.fetch_all(
        """
        SELECT c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relkind IN ('r','p')
          AND c.relname = ANY(%s)
        """,
        [REQUIRED_OPERATOR_TABLES],
    )
    present = {str(row['table_name']) for row in rows}
    missing = [name for name in REQUIRED_OPERATOR_TABLES if name not in present]
    return not missing, missing


def ensure_database_ready(app: Any) -> dict[str, Any]:
    """Ленивая проверка PostgreSQL для операторской панели.

    `python main.py serve --mode testnet` запускается в безопасном локальном
    режиме и не обязан падать, если PostgreSQL еще не готов. Поэтому startup
    может оставить app.state.db_available=False. После того как оператор нажал
    «Применить migrations», backend должен сам перепроверить БД и перевести
    workflow дальше без перезапуска сервера и без консольных действий.

    Возвращает два уровня готовности:
    - connection_ok: сервер PostgreSQL доступен;
    - schema_ready: применены таблицы hard-invariants/audit/evidence.
    """

    settings = app.state.settings
    current_db = getattr(app.state, 'db', None)

    if current_db is not None:
        try:
            current_db.fetch_one('SELECT 1 AS ok')
            schema_ready, missing = _tables_ready(current_db)
            app.state.db_available = True
            app.state.db_schema_ready = schema_ready
            app.state.db_missing_tables = missing
            app.state.db_startup_error = None if schema_ready else 'migrations_missing:' + ','.join(missing)
            if schema_ready and getattr(app.state, 'repository', None) is None:
                app.state.repository = Repository(current_db)
            return {
                'connection_ok': True,
                'schema_ready': schema_ready,
                'missing_tables': missing,
                'error': app.state.db_startup_error,
            }
        except Exception as exc:
            try:
                current_db.close()
            except Exception:
                pass
            app.state.db = None
            app.state.repository = None
            app.state.db_available = False
            app.state.db_schema_ready = False
            app.state.db_missing_tables = REQUIRED_OPERATOR_TABLES[:]
            app.state.db_startup_error = f'{type(exc).__name__}:{exc}'

    try:
        db = Database(settings.database_url)
        db.open()
        db.fetch_one('SELECT 1 AS ok')
        schema_ready, missing = _tables_ready(db)
    except Exception as exc:
        try:
            db.close()  # type: ignore[name-defined]
        except Exception:
            pass
        app.state.db = None
        app.state.repository = None
        app.state.db_available = False
        app.state.db_schema_ready = False
        app.state.db_missing_tables = REQUIRED_OPERATOR_TABLES[:]
        app.state.db_startup_error = f'{type(exc).__name__}:{exc}'
        return {
            'connection_ok': False,
            'schema_ready': False,
            'missing_tables': REQUIRED_OPERATOR_TABLES[:],
            'error': app.state.db_startup_error,
        }

    app.state.db = db
    app.state.db_available = True
    app.state.db_schema_ready = schema_ready
    app.state.db_missing_tables = missing
    app.state.db_startup_error = None if schema_ready else 'migrations_missing:' + ','.join(missing)
    app.state.repository = Repository(db) if schema_ready else None
    return {
        'connection_ok': True,
        'schema_ready': schema_ready,
        'missing_tables': missing,
        'error': app.state.db_startup_error,
    }

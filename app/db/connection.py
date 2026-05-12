from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterable
import os


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class Database:
    def __init__(self, database_url: str, pool_timeout: float | None = None, connect_timeout: float | None = None):
        try:
            from psycopg.rows import dict_row  # type: ignore
            from psycopg_pool import ConnectionPool  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - зависит от окружения.
            raise RuntimeError('psycopg_pool_required_for_postgresql') from exc

        # Fail-fast defaults критичны для CLI preflight: недоступная PostgreSQL
        # должна быстро вернуть BLOCKED, а не зависать на долгих pool-retry.
        self.pool_timeout = pool_timeout if pool_timeout is not None else _float_env('CAS_DB_POOL_TIMEOUT', 1.0)
        self.connect_timeout = connect_timeout if connect_timeout is not None else _float_env('CAS_DB_CONNECT_TIMEOUT', 1.0)
        self.pool = ConnectionPool(
            database_url,
            min_size=0,
            max_size=5,
            timeout=self.pool_timeout,
            reconnect_timeout=self.pool_timeout,
            kwargs={'row_factory': dict_row, 'connect_timeout': self.connect_timeout},
            open=False,
        )

    def open(self) -> None:
        self.pool.open()

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def connection(self):
        with self.pool.connection(timeout=self.pool_timeout) as conn:
            yield conn

    def fetch_all(self, sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                return list(cur.fetchall())

    def fetch_one(self, sql: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
            conn.commit()

    def execute_returning_one(self, sql: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                row = cur.fetchone()
            conn.commit()
            return row

from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Iterable


class Database:
    def __init__(self, database_url: str):
        try:
            from psycopg.rows import dict_row  # type: ignore
            from psycopg_pool import ConnectionPool  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - зависит от окружения.
            raise RuntimeError('psycopg_pool_required_for_postgresql') from exc
        self.pool = ConnectionPool(database_url, min_size=1, max_size=5, kwargs={'row_factory': dict_row}, open=False)

    def open(self) -> None:
        self.pool.open()

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def connection(self):
        with self.pool.connection() as conn:
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

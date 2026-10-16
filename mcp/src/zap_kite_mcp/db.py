from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from importlib import resources
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

Row = dict[str, Any]
Params = Sequence[Any]

_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


class Database:
    def __init__(self, url: str, max_size: int = 8) -> None:
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=max_size,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=True,
        )

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Row]]:
        with self._pool.connection() as conn:
            yield cast(psycopg.Connection[Row], conn)

    def query(self, sql: str, params: Params = ()) -> list[Row]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else []

    def one(self, sql: str, params: Params = ()) -> Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Params = ()) -> int:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def migrate(self) -> list[str]:
        """Apply packaged SQL migrations that are not yet recorded; returns the applied names."""
        applied: list[str] = []
        with self.connection() as conn, conn.transaction():
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            conn.execute("LOCK TABLE schema_migrations IN EXCLUSIVE MODE")
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM schema_migrations")
                done = {r["name"] for r in cur.fetchall()}
            for name, sql in _migrations():
                if name in done:
                    continue
                conn.execute(sql)
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (name,))
                applied.append(name)
        return applied


def _migrations() -> list[tuple[str, str]]:
    folder = resources.files("zap_kite_mcp").joinpath("migrations")
    found = [(p.name, p.read_text()) for p in folder.iterdir() if _MIGRATION_NAME.match(p.name)]
    return sorted(found)

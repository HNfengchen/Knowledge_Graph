from __future__ import annotations

import asyncpg

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger

log = get_logger(__name__)

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
    username       VARCHAR(255) PRIMARY KEY,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class PostgresClient:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls) -> PostgresClient:
        s = get_settings()
        pool = await asyncpg.create_pool(
            host=s.POSTGRES_HOST,
            port=s.POSTGRES_PORT,
            user=s.POSTGRES_USER,
            password=s.POSTGRES_PASSWORD,
            database=s.POSTGRES_DATABASE,
            min_size=1,
            max_size=s.POSTGRES_POOL_SIZE,
        )
        async with pool.acquire() as conn:
            await conn.execute(_INIT_SQL)
        log.info("pg_connected", host=s.POSTGRES_HOST, port=s.POSTGRES_PORT)
        return cls(pool)

    async def execute(self, sql: str, *args: object) -> str:
        async with self._pool.acquire() as conn:
            return await conn.execute(sql, *args)

    async def fetchrow(self, sql: str, *args: object) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None

    async def fetch(self, sql: str, *args: object) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    async def close(self) -> None:
        await self._pool.close()
        log.info("pg_disconnected")

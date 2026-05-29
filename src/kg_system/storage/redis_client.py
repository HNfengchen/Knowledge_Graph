from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger

log = get_logger(__name__)


class RedisClient:
    """异步 Redis 连接池封装。提供 get_client() 拿到 Redis 实例。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls) -> "RedisClient":
        s = get_settings()
        pool = ConnectionPool(
            host=s.REDIS_HOST,
            port=s.REDIS_PORT,
            password=s.REDIS_PASSWORD or None,
            db=s.REDIS_DB,
            ssl=s.REDIS_SSL,
            decode_responses=s.REDIS_DECODE_RESPONSES,
            max_connections=50,
        )
        client = Redis(connection_pool=pool)
        try:
            await client.ping()
        except Exception as e:
            await pool.disconnect()
            raise RuntimeError(f"failed to connect Redis: {e}") from e
        finally:
            await client.close()
        log.info("redis_connected", host=s.REDIS_HOST, port=s.REDIS_PORT, db=s.REDIS_DB)
        return cls(pool)

    def get_client(self) -> Redis:
        return Redis(connection_pool=self._pool)

    async def close(self) -> None:
        await self._pool.disconnect()

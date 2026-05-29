"""LLM 调用埋点流消费者（骨架占位）。

骨架阶段：仅启动空 task，等待停止事件，不消费 Redis Stream 数据。
"""
from __future__ import annotations

import asyncio

from kg_system.core.logging import get_logger
from kg_system.storage.redis_client import RedisClient

logger = get_logger(__name__)


class StreamCollector:
    """从 Redis Stream 读取 LLM 调用事件并聚合（骨架阶段：空跑）。"""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="stream-collector")
        logger.info("stream_collector_started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        logger.info("stream_collector_stopped")

    async def _run(self) -> None:
        # 骨架阶段：不实际消费数据，等待停止信号即可。
        await self._stop.wait()

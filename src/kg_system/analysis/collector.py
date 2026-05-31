"""LLM 调用埋点流消费者。

从 Redis Stream 读取事件，按分钟桶聚合到 Redis Hash。
"""
from __future__ import annotations

import asyncio
import time

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.storage.redis_client import RedisClient

logger = get_logger(__name__)


class StreamCollector:
    """从 Redis Stream 读取 LLM 调用事件并聚合到分钟桶。"""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._settings = get_settings()

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

    async def _ensure_group(self, r, stream_key: str, group: str) -> None:
        try:
            await r.xgroup_create(stream_key, group, id="0", mkstream=True)
        except Exception:
            pass  # group 已存在

    async def _run(self) -> None:
        s = self._settings
        stream_key = s.REDIS_STREAM_KEY
        group = "analysis"
        consumer = f"collector-{id(self)}"
        prefix = s.REDIS_KEY_PREFIX
        metrics_prefix = s.REDIS_METRICS_PREFIX

        r = self._redis.get_client()
        try:
            await self._ensure_group(r, stream_key, group)
        except Exception as e:
            logger.warning("stream_group_setup_failed", error=str(e))

        while not self._stop.is_set():
            try:
                results = await r.xreadgroup(
                    group, consumer, {stream_key: ">"}, count=100, block=1000
                )
            except Exception as e:
                logger.warning("stream_read_failed", error=str(e))
                await asyncio.sleep(1)
                continue

            for stream, messages in results:
                for msg_id, msg_data in messages:
                    try:
                        self._process_message(msg_data, prefix, metrics_prefix, r)
                        await r.xack(stream_key, group, msg_id)
                    except Exception as e:
                        logger.warning("stream_process_failed", error=str(e), msg_id=msg_id)

        await r.close()

    def _process_message(self, data: dict, prefix: str, metrics_prefix: str, r) -> None:
        event_type = data.get("type", "llm_call")
        ts = int(time.time())
        bucket = ts // 60
        bucket_key = f"{prefix}{metrics_prefix}{bucket}"
        latency_key = f"{prefix}latency:{bucket}"

        if event_type == "llm_call":
            duration = float(data.get("duration_ms", 0))
            prompt_tokens = int(data.get("prompt_tokens", 0))
            completion_tokens = int(data.get("completion_tokens", 0))
            has_error = 1 if data.get("error") else 0

            pipeline = r.pipeline()
            pipeline.hincrby(bucket_key, "count", 1)
            pipeline.hincrby(bucket_key, "total_duration", int(duration))
            pipeline.hincrby(bucket_key, "total_prompt_tokens", prompt_tokens)
            pipeline.hincrby(bucket_key, "total_completion_tokens", completion_tokens)
            pipeline.hincrby(bucket_key, "errors", has_error)
            pipeline.execute()

            r.zadd(latency_key, {str(ts): duration})
            r.expire(bucket_key, 604800)  # 7 天
            r.expire(latency_key, 604800)

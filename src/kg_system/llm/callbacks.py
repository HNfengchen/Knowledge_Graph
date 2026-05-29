from __future__ import annotations

import json
import time
import uuid
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.storage.redis_client import RedisClient

log = get_logger(__name__)


class AnalysisCallbackHandler(AsyncCallbackHandler):
    """LLM 调用埋点。生命周期事件写入 Redis Stream。"""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._starts: dict[str, float] = {}

    @staticmethod
    def _ev(event_type: str, call_id: str, **fields: Any) -> dict[str, str]:
        ev = {
            "event_id": str(uuid.uuid4()),
            "call_id": call_id,
            "event_type": event_type,
            "timestamp_ms": str(int(time.time() * 1000)),
            **{k: json.dumps(v) if not isinstance(v, str) else v for k, v in fields.items()},
        }
        return ev

    async def _emit(self, event: dict[str, str]) -> None:
        s = get_settings()
        client = self._redis.get_client()
        try:
            await client.xadd(s.REDIS_STREAM_KEY, event, maxlen=100000, approximate=True)
        finally:
            await client.close()

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        call_id = str(run_id)
        self._starts[call_id] = time.time()
        await self._emit(
            self._ev(
                "on_llm_start",
                call_id,
                model_name=str(serialized.get("name", "unknown")),
                prompt_count=str(len(prompts)),
            )
        )
    async def on_llm_end(self, response: LLMResult, *, run_id: uuid.UUID, **kwargs: Any) -> None:
        call_id = str(run_id)
        started = self._starts.pop(call_id, None)
        duration_ms = int((time.time() - started) * 1000) if started else 0
        usage = (response.llm_output or {}).get("token_usage", {}) if response.llm_output else {}
        await self._emit(
            self._ev(
                "on_llm_end",
                call_id,
                duration_ms=str(duration_ms),
                input_tokens=str(usage.get("prompt_tokens", 0)),
                output_tokens=str(usage.get("completion_tokens", 0)),
                status="success",
            )
        )

    async def on_llm_error(
        self, error: BaseException, *, run_id: uuid.UUID, **kwargs: Any
    ) -> None:
        call_id = str(run_id)
        started = self._starts.pop(call_id, None)
        duration_ms = int((time.time() - started) * 1000) if started else 0
        await self._emit(
            self._ev(
                "on_llm_error",
                call_id,
                duration_ms=str(duration_ms),
                status="error",
                error_message=str(error)[:500],
            )
        )

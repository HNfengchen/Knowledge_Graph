from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.llm.factory import get_embedding_model
from kg_system.storage.redis_client import RedisClient

log = get_logger(__name__)


class SemanticCache:
    """语义缓存：用 embedding 相似度匹配近似 prompt。

    缓存键：{prefix}sc:{provider}:{model}:{sha256(prompt+params)}
    向量索引：在 Redis 中用 KV + 本地内存 ANN；退化到精确匹配。
    """

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._settings = get_settings()
        self._embedding_model = None
        self._local_cache: dict[str, dict] = {}
        self._local_embeddings: list[tuple[list[float], str]] = []

    def _cache_key(self, provider: str, model: str, prompt: str, params: dict) -> str:
        raw = f"{prompt}:{json.dumps(params, sort_keys=True)}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{self._settings.REDIS_KEY_PREFIX}sc:{provider}:{model}:{h}"

    async def _get_embedding(self, text: str) -> list[float] | None:
        if self._embedding_model is None:
            try:
                self._embedding_model = get_embedding_model()
            except Exception as e:
                log.warning("cache_embedding_unavailable", error=str(e))
                return None
        try:
            return await self._embedding_model.aembed_query(text)
        except Exception as e:
            log.warning("cache_embedding_failed", error=str(e))
            return None

    def _cosine_sim(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if not na or not nb:
            return 0.0
        return dot / (na * nb)

    async def get(
        self,
        prompt: str,
        provider: str = "openai",
        model: str = "",
        params: dict | None = None,
    ) -> str | None:
        if not self._settings.SEMANTIC_CACHE_ENABLED:
            return None
        params = params or {}
        threshold = self._settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD

        prompt_emb = await self._get_embedding(prompt)
        if prompt_emb is None:
            exact_key = self._cache_key(provider, model, prompt, params)
            return await self._redis_get(exact_key)

        best_score = 0.0
        best_key = None
        for emb, key in self._local_embeddings:
            score = self._cosine_sim(prompt_emb, emb)
            if score > best_score:
                best_score = score
                best_key = key

        if best_score >= threshold and best_key:
            cached = await self._redis_get(best_key)
            if cached:
                log.info("cache_hit", score=round(best_score, 3), key=best_key)
                return cached

        log.info("cache_miss", best_score=round(best_score, 3))
        return None

    async def set(
        self,
        prompt: str,
        response: str,
        provider: str = "openai",
        model: str = "",
        params: dict | None = None,
    ) -> None:
        if not self._settings.SEMANTIC_CACHE_ENABLED:
            return
        params = params or {}
        key = self._cache_key(provider, model, prompt, params)

        prompt_emb = await self._get_embedding(prompt)
        if prompt_emb:
            self._local_embeddings.append((prompt_emb, key))
            if len(self._local_embeddings) > self._settings.SEMANTIC_CACHE_MAX_SIZE:
                self._local_embeddings.pop(0)

        ttl = self._settings.SEMANTIC_CACHE_TTL
        redis = self._redis.get_client()
        try:
            await redis.setex(key, ttl, response)
        except Exception as e:
            log.warning("cache_write_failed", error=str(e))
        finally:
            await redis.close()

    async def _redis_get(self, key: str) -> str | None:
        redis = self._redis.get_client()
        try:
            val = await redis.get(key)
            return val
        except Exception as e:
            log.warning("cache_read_failed", error=str(e))
            return None
        finally:
            await redis.close()


def with_semantic_cache(model: BaseChatModel, cache: SemanticCache) -> BaseChatModel:
    """包装 BaseChatModel 使其先查语义缓存。"""
    original_ainvoke = model.ainvoke

    async def cached_ainvoke(*args, **kwargs):
        messages = args[0] if args else kwargs.get("messages", [])
        prompt = " ".join(str(m.content) for m in messages) if messages else ""
        provider = getattr(model, "_llm_type", "unknown")
        model_name = getattr(model, "model", "") or getattr(model, "model_name", "")
        params = {"temperature": getattr(model, "temperature", 0.0)}

        cached = await cache.get(prompt, provider=provider, model=model_name, params=params)
        if cached:
            return AIMessage(content=cached)

        result = await original_ainvoke(*args, **kwargs)
        content = str(result.content) if hasattr(result, "content") else str(result)
        await cache.set(prompt, content, provider=provider, model=model_name, params=params)
        return result

    model.ainvoke = cached_ainvoke  # type: ignore
    return model

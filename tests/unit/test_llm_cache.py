from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from langchain_core.messages import AIMessage

from kg_system.llm.cache import SemanticCache, with_semantic_cache
from kg_system.storage.redis_client import RedisClient


def _make_redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    r.close = AsyncMock(return_value=None)
    return r


class _MockModel:
    """非 pydantic 模型，避免 with_semantic_cache 赋值 ainvoke 时报错。"""
    _llm_type = "mock"
    temperature = 0.0

    def __init__(self, response: str = "mock response") -> None:
        self._response = response

    async def ainvoke(self, messages: list, **kwargs) -> AIMessage:
        return AIMessage(content=self._response)


class TestCacheKey:
    def test_deterministic(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        k1 = cache._cache_key("openai", "gpt-4", "hello", {"temp": 0.5})
        k2 = cache._cache_key("openai", "gpt-4", "hello", {"temp": 0.5})
        assert k1 == k2

    def test_different_inputs_different_keys(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        k1 = cache._cache_key("openai", "gpt-4", "hello", {})
        k2 = cache._cache_key("openai", "gpt-4", "world", {})
        assert k1 != k2

    def test_prefix_and_components(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        key = cache._cache_key("anthropic", "claude-3", "test", {})
        assert key.startswith("kg:sc:anthropic:claude-3:")

    def test_params_affect_key(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        k1 = cache._cache_key("openai", "gpt-4", "hello", {"temp": 0.5})
        k2 = cache._cache_key("openai", "gpt-4", "hello", {"temp": 0.7})
        assert k1 != k2

    def test_params_sorting_is_deterministic(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        k1 = cache._cache_key("o", "m", "p", {"b": 2, "a": 1})
        k2 = cache._cache_key("o", "m", "p", {"a": 1, "b": 2})
        assert k1 == k2

    def test_empty_params(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        key = cache._cache_key("o", "m", "p", {})
        assert key is not None
        assert key.count(":") == 4


class TestCosineSim:
    def test_identical(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        v = [1.0, 2.0, 3.0]
        assert cache._cosine_sim(v, v) == pytest.approx(1.0)

    def test_orthogonal(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        assert cache._cosine_sim([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_partial_similarity(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        s = cache._cosine_sim([1, 2, 3], [4, 5, 6])
        assert s == pytest.approx(0.9746, rel=1e-3)

    def test_zero_first_vector(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        assert cache._cosine_sim([0, 0, 0], [1, 2, 3]) == 0.0

    def test_zero_second_vector(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        assert cache._cosine_sim([1, 2, 3], [0, 0, 0]) == 0.0

    def test_both_zero_vectors(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        assert cache._cosine_sim([0, 0], [0, 0]) == 0.0

    def test_negative_vectors(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        s = cache._cosine_sim([-1, -2], [1, 2])
        assert s == pytest.approx(-1.0)

    def test_single_element_vectors(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        assert cache._cosine_sim([5], [5]) == pytest.approx(1.0)
        assert cache._cosine_sim([5], [-5]) == pytest.approx(-1.0)


class TestSemanticCacheGet:
    @pytest.fixture
    def cache(self):
        redis_client = MagicMock(spec=RedisClient)
        redis_client.get_client.return_value = _make_redis()
        return SemanticCache(redis_client)

    async def test_disabled_returns_none(self, cache):
        cache._settings.SEMANTIC_CACHE_ENABLED = False
        result = await cache.get("hello")
        assert result is None

    async def test_embedding_unavailable_falls_back_to_exact_match(self, cache):
        with patch("kg_system.llm.cache.get_embedding_model", side_effect=Exception("fail")):
            key = cache._cache_key("openai", "", "hello", {})
            redis = cache._redis.get_client()
            await redis.setex(key, 3600, "exact match")
            result = await cache.get("hello")
            assert result == "exact match"

    async def test_embedding_unavailable_and_no_exact_match_returns_none(self, cache):
        with patch("kg_system.llm.cache.get_embedding_model", side_effect=Exception("fail")):
            result = await cache.get("hello")
            assert result is None

    async def test_semantic_match_returns_cached_value(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        cache._local_embeddings.append(([1.0, 0.0], "cache_key"))
        redis = cache._redis.get_client()
        await redis.setex("cache_key", 3600, "cached value")
        result = await cache.get("hello")
        assert result == "cached value"

    async def test_logs_hit_info(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        cache._local_embeddings.append(([1.0, 0.0], "cache_key"))
        redis = cache._redis.get_client()
        await redis.setex("cache_key", 3600, "val")
        with patch("kg_system.llm.cache.log.info") as mock_info:
            await cache.get("hello")
            mock_info.assert_called_once()
            args, _ = mock_info.call_args
            assert args[0] == "cache_hit"

    async def test_below_threshold_returns_none(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        cache._local_embeddings.append(([0.0, 1.0], "some_key"))
        result = await cache.get("hello")
        assert result is None

    async def test_no_local_embeddings_returns_none(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        result = await cache.get("hello")
        assert result is None

    async def test_match_in_redis_but_not_in_local_embeddings_is_miss(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        redis = cache._redis.get_client()
        await redis.setex("orphan_key", 3600, "orphan")
        result = await cache.get("hello")
        assert result is None


class TestSemanticCacheSet:
    @pytest.fixture
    def cache(self):
        redis_client = MagicMock(spec=RedisClient)
        redis_client.get_client.return_value = _make_redis()
        return SemanticCache(redis_client)

    async def test_disabled_does_not_write(self, cache):
        cache._settings.SEMANTIC_CACHE_ENABLED = False
        await cache.set("hello", "world")
        key = cache._cache_key("openai", "", "hello", {})
        redis = cache._redis.get_client()
        val = await redis.get(key)
        assert val is None

    async def test_writes_to_redis(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        await cache.set("hello", "world")
        key = cache._cache_key("openai", "", "hello", {})
        redis = cache._redis.get_client()
        val = await redis.get(key)
        assert val == "world"

    async def test_updates_local_embedding_index(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        await cache.set("hello", "world")
        key = cache._cache_key("openai", "", "hello", {})
        assert len(cache._local_embeddings) == 1
        assert cache._local_embeddings[0][1] == key

    async def test_evicts_oldest_when_max_size_reached(self, cache):
        cache._settings.SEMANTIC_CACHE_MAX_SIZE = 2
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.set("c", "3")
        assert len(cache._local_embeddings) == 2
        keys = {k for _, k in cache._local_embeddings}
        assert cache._cache_key("openai", "", "a", {}) not in keys
        assert cache._cache_key("openai", "", "b", {}) in keys
        assert cache._cache_key("openai", "", "c", {}) in keys

    async def test_redis_write_failure_logged_gracefully(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        bad_redis = AsyncMock()
        bad_redis.setex.side_effect = Exception("write error")
        cache._redis.get_client.return_value = bad_redis
        await cache.set("hello", "world")
        assert len(cache._local_embeddings) == 1

    async def test_no_embedding_skips_local_index_but_writes_redis(self, cache):
        with patch("kg_system.llm.cache.get_embedding_model", side_effect=Exception("fail")):
            await cache.set("hello", "world")
            key = cache._cache_key("openai", "", "hello", {})
            redis = cache._redis.get_client()
            val = await redis.get(key)
            assert val == "world"
            assert len(cache._local_embeddings) == 0

    async def test_default_params_used(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        await cache.set("hello", "world")
        key = cache._cache_key("openai", "", "hello", {})
        assert key is not None

    async def test_embeddings_failure_skips_local_index_but_writes_redis(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.side_effect = Exception("fail")
        await cache.set("hello", "world")
        key = cache._cache_key("openai", "", "hello", {})
        redis = cache._redis.get_client()
        val = await redis.get(key)
        assert val == "world"
        assert len(cache._local_embeddings) == 0


class TestRedisGet:
    async def test_returns_none_on_read_error(self):
        cache = SemanticCache(MagicMock(spec=RedisClient))
        bad_redis = AsyncMock()
        bad_redis.get.side_effect = Exception("read error")
        cache._redis.get_client.return_value = bad_redis
        result = await cache._redis_get("somekey")
        assert result is None

    async def test_returns_value_on_success(self):
        r = _make_redis()
        await r.set("my_key", "my_val")
        redis_client = MagicMock(spec=RedisClient)
        redis_client.get_client.return_value = r
        cache = SemanticCache(redis_client)
        result = await cache._redis_get("my_key")
        assert result == "my_val"

    async def test_returns_none_for_missing_key(self):
        r = _make_redis()
        redis_client = MagicMock(spec=RedisClient)
        redis_client.get_client.return_value = r
        cache = SemanticCache(redis_client)
        result = await cache._redis_get("nonexistent")
        assert result is None


class TestWithSemanticCache:
    @pytest.fixture
    def cache(self):
        redis_client = MagicMock(spec=RedisClient)
        redis_client.get_client.return_value = _make_redis()
        return SemanticCache(redis_client)

    async def test_returns_cached_response_on_hit(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        key = cache._cache_key("mock", "", "hello", {"temperature": 0.0})
        cache._local_embeddings.append(([1.0, 0.0], key))
        redis = cache._redis.get_client()
        await redis.setex(key, 3600, "cached response")
        model = _MockModel()
        wrapped = with_semantic_cache(model, cache)
        result = await wrapped.ainvoke([MagicMock(content="hello")])
        assert result.content == "cached response"

    async def test_calls_original_and_caches_on_miss(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        model = _MockModel(response="original response")
        wrapped = with_semantic_cache(model, cache)
        result = await wrapped.ainvoke([MagicMock(content="hello")])
        assert result.content == "original response"
        key = cache._cache_key("mock", "", "hello", {"temperature": 0.0})
        redis = cache._redis.get_client()
        val = await redis.get(key)
        assert val == "original response"

    async def test_caches_with_temperature_param(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        model = _MockModel()
        model.temperature = 0.7
        wrapped = with_semantic_cache(model, cache)
        await wrapped.ainvoke([MagicMock(content="hello")])
        key = cache._cache_key("mock", "", "hello", {"temperature": 0.7})
        redis = cache._redis.get_client()
        val = await redis.get(key)
        assert val is not None

    async def test_wraps_model_ainvoke(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        model = _MockModel()
        original = model.ainvoke
        wrapped = with_semantic_cache(model, cache)
        assert model.ainvoke is not original
        result = await wrapped.ainvoke([MagicMock(content="hello")])
        assert result.content == "mock response"

    async def test_passes_kwargs_to_original(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        model = _MockModel(response="kwarg works")
        wrapped = with_semantic_cache(model, cache)
        result = await wrapped.ainvoke(messages=[MagicMock(content="hello")])
        assert result.content == "kwarg works"

    async def test_logs_miss_when_cache_empty(self, cache):
        cache._embedding_model = AsyncMock()
        cache._embedding_model.aembed_query.return_value = [1.0, 0.0]
        model = _MockModel()
        with patch("kg_system.llm.cache.log.info") as mock_info:
            wrapped = with_semantic_cache(model, cache)
            await wrapped.ainvoke([MagicMock(content="hello")])
            mock_info.assert_any_call("cache_miss", best_score=0.0)

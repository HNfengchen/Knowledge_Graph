from __future__ import annotations

from kg_system.core.exceptions import (
    AuthError,
    ConfigError,
    EntityNotFound,
    InvalidInput,
    KGException,
    LLMError,
    LLMTimeoutError,
    Neo4jError,
    NotImplementedInSkeleton,
    RateLimitError,
)


class TestKGExceptionHierarchy:
    def test_base_exception(self):
        exc = KGException("something wrong")
        assert exc.code == 500
        assert exc.msg == "something wrong"

    def test_config_error(self):
        exc = ConfigError("bad config")
        assert exc.code == 500
        assert "config" in exc.msg

    def test_llm_error(self):
        exc = LLMError("llm failed")
        assert exc.code == 502

    def test_llm_timeout(self):
        exc = LLMTimeoutError("timeout")
        assert exc.code == 504

    def test_neo4j_error(self):
        exc = Neo4jError("db down")
        assert exc.code == 503

    def test_entity_not_found(self):
        exc = EntityNotFound("missing")
        assert exc.code == 404

    def test_invalid_input(self):
        exc = InvalidInput("bad input")
        assert exc.code == 400

    def test_auth_error(self):
        exc = AuthError("unauthorized")
        assert exc.code == 401

    def test_rate_limit(self):
        exc = RateLimitError("too fast")
        assert exc.code == 429

    def test_not_implemented(self):
        exc = NotImplementedInSkeleton("not yet")
        assert exc.code == 501

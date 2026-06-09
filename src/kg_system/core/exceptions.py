from __future__ import annotations


class KGException(Exception):
    """所有业务异常的基类。"""

    code: int = 500
    msg: str = "internal error"

    def __init__(self, msg: str | None = None, *, code: int | None = None) -> None:
        if msg is not None:
            self.msg = msg
        if code is not None:
            self.code = code
        super().__init__(self.msg)


class ConfigError(KGException):
    code = 500
    msg = "configuration error"


class LLMError(KGException):
    code = 502
    msg = "LLM service error"


class LLMTimeoutError(LLMError):
    code = 504


class RequestTimeout(KGException):
    code = 504
    msg = "request timed out"
    msg = "LLM call timeout"


class Neo4jError(KGException):
    code = 503
    msg = "Neo4j error"


class EntityNotFound(KGException):
    code = 404
    msg = "entity not found"


class InvalidInput(KGException):
    code = 400
    msg = "invalid input"


class AuthError(KGException):
    code = 401
    msg = "unauthorized"


class RateLimitError(KGException):
    code = 429
    msg = "rate limit exceeded"


class NotImplementedInSkeleton(KGException):
    code = 501
    msg = "not implemented in skeleton"

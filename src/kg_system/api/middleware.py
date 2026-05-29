from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kg_system.core.exceptions import KGException
from kg_system.core.logging import get_logger
from kg_system.core.models import ApiResponse

log = get_logger(__name__)


def _envelope(code: int, msg: str, data=None) -> JSONResponse:
    body = ApiResponse(code=code, msg=msg, data=data).model_dump()
    return JSONResponse(status_code=code if 100 <= code < 600 else 500, content=body)


def install_middleware_and_handlers(app: FastAPI) -> None:
    """注册请求 ID 中间件 + 三个异常处理器。"""

    @app.middleware("http")
    async def request_id_mw(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = rid
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_unhandled", request_id=rid, path=request.url.path)
            raise
        response.headers["X-Request-ID"] = rid
        log.info(
            "request_done",
            request_id=rid,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=int((time.time() - start) * 1000),
        )
        return response

    @app.exception_handler(KGException)
    async def kg_exc_handler(request: Request, exc: KGException):
        log.warning("kg_exception", code=exc.code, msg=exc.msg, path=request.url.path)
        return _envelope(exc.code, exc.msg)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return _envelope(400, "invalid request", data={"errors": exc.errors()})

    @app.exception_handler(Exception)
    async def fallback_handler(request: Request, exc: Exception):
        log.exception("unhandled_exception", path=request.url.path)
        return _envelope(500, "internal error")

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kg_system.analysis.collector import StreamCollector
from kg_system.api.middleware import install_middleware_and_handlers
from kg_system.api.v1.analysis import router as analysis_router
from kg_system.api.v1.auth import router as auth_router
from kg_system.api.v1.external import router as external_router
from kg_system.api.v1.kg import router as kg_router
from kg_system.api.v1.reason import router as reason_router
from kg_system.core.config import get_settings
from kg_system.core.logging import configure_logging, get_logger
from kg_system.core.models import ApiResponse
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.postgres_client import PostgresClient
from kg_system.storage.redis_client import RedisClient
from kg_system.storage.schemas import apply_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger("kg_system.main")
    s = get_settings()
    log.info("startup_begin", env=s.APP_ENV)

    app.state.neo4j = await Neo4jClient.create()
    app.state.redis = await RedisClient.create()
    await apply_schema(app.state.neo4j)
    app.state.collector = StreamCollector(app.state.redis)
    await app.state.collector.start()

    try:
        app.state.postgres = await PostgresClient.create()
        if s.ADMIN_USERNAME and s.ADMIN_PASSWORD:
            import hashlib
            from kg_system.storage.user_repo import UserRepo
            repo = UserRepo(app.state.postgres)
            admin = await repo.get_user(s.ADMIN_USERNAME)
            if not admin:
                pw_hash = hashlib.sha256(s.ADMIN_PASSWORD.encode()).hexdigest()
                await repo.create_user(s.ADMIN_USERNAME, pw_hash, role="admin")
                log.info("admin_seeded", username=s.ADMIN_USERNAME)
    except Exception:
        log.warning("postgres_unavailable", exc_info=True)
        app.state.postgres = None

    log.info("startup_done")
    try:
        yield
    finally:
        log.info("shutdown_begin")
        await app.state.collector.stop()
        await app.state.redis.close()
        await app.state.neo4j.close()
        if hasattr(app.state, "postgres") and app.state.postgres:
            await app.state.postgres.close()
        log.info("shutdown_done")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.APP_NAME,
        version="0.1.0",
        debug=s.APP_DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins_list,
        allow_credentials=s.CORS_ALLOW_CREDENTIALS,
        allow_methods=[m.strip() for m in s.CORS_ALLOW_METHODS.split(",")],
        allow_headers=[h.strip() for h in s.CORS_ALLOW_HEADERS.split(",")],
    )
    install_middleware_and_handlers(app)

    @app.get("/health", response_model=ApiResponse[dict])
    async def health() -> ApiResponse[dict]:
        return ApiResponse(data={"status": "ok"})

    app.include_router(kg_router, prefix="/api/v1")
    app.include_router(reason_router, prefix="/api/v1")
    app.include_router(analysis_router, prefix="/api/v1")
    app.include_router(external_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")

    return app


app = create_app()

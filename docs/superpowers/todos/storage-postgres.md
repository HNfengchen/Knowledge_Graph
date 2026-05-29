# storage/postgres —— 业务关系表

## 目标

为非图谱业务数据（用户、API Key、构建作业、外部审计、配额等）落地关系型存储。docker-compose 已起 Postgres 容器，但代码侧无任何 ORM / DSN 消费。

## 当前状态

- `docker-compose.yml` 含 `postgres:16-alpine` 服务，端口 5432，库名 `kgdb`，密码取自 env。
- 代码仓内 **无** SQLAlchemy / asyncpg / alembic 依赖。
- `core/config.py` 无 `POSTGRES_*` 字段。

## 范围

- **入**：业务侧需求驱动（auth、external API key、build job log、配额计费）。
- **出**：异步 ORM session、迁移管线、CRUD service。
- **不在范围**：把图数据搬到 Postgres；多租户分库。

## 子任务

- [ ] **T1：依赖与配置**
  - `pyproject.toml` 增 `sqlalchemy[asyncio]>=2.0`、`asyncpg>=0.29`、`alembic>=1.13`。
  - `core/config.py` 增 `POSTGRES_DSN`（默认 `postgresql+asyncpg://kg:kg@localhost:5432/kgdb`）+ `POSTGRES_POOL_SIZE` (10) + `POSTGRES_MAX_OVERFLOW` (20)。
  - 验收：`get_settings().POSTGRES_DSN` 可解析。

- [ ] **T2：engine + session**
  - 新增 `src/kg_system/storage/postgres_client.py`：`create_async_engine` + `async_sessionmaker(expire_on_commit=False)`。
  - `api/deps.py` 增 `get_pg_session() -> AsyncIterator[AsyncSession]`。
  - lifespan：启动 `engine.connect()` ping 一次确认可达。
  - 验收：`/health` 增加 `postgres: ok|fail` 字段。

- [ ] **T3：基础模型**
  - `src/kg_system/storage/orm/__init__.py` + `base.py:Base = DeclarativeBase`。
  - 表初版（每张一个文件）：
    - `users.py`：`User(id UUID, username, password_hash, role, created_at)` —— 由 [auth.md](./auth.md) 消费。
    - `api_keys.py`：`ApiKey(id, key_hash, owner_user_id FK, scopes JSON, expires_at, last_used_at)`。
    - `build_jobs.py`：`BuildJob(id, doc_id, status, chunks, entities, relations, started_at, finished_at, error)`。
    - `audit_logs.py`：`AuditLog(id, ts, request_id, api_key_id?, endpoint, status, payload_size, duration_ms)`。
  - 验收：`Base.metadata.create_all` 在 fresh DB 上无错。

- [ ] **T4：Alembic 集成**
  - 初始化 `alembic/`；env.py 用 `target_metadata = Base.metadata` + `POSTGRES_DSN`。
  - 第一版迁移 `0001_init.py`。
  - `python -m alembic upgrade head` 在 docker-compose 启动后自动跑（添加 init container 或 entrypoint 钩子）。
  - 验收：fresh 起容后所有表存在。

- [ ] **T5：repository 层**
  - 每张表一个 repository（`src/kg_system/storage/repos/users_repo.py` 等），方法 async + `AsyncSession`。
  - 禁止在 router 直接写 SQL，统一过 repo。
  - 验收：单测覆盖 CRUD 主路径。

- [ ] **T6：BuildJob 接入 build pipeline**
  - 在 `KGBuildPipeline.run` 入口插入 `BuildJob(status=running)`，结束更新 `status=succeeded|failed`。
  - 失败回填 `error` 字段（截断 1k 字符）。
  - 验收：跑一次 `/kg/build` 后 `SELECT * FROM build_jobs` 出现 1 条。

- [ ] **T7：观测**
  - SQLAlchemy `event.listens_for("before_cursor_execute"/"after_cursor_execute")` 收集慢查询，超 `PG_SLOW_QUERY_MS`（200ms）记 warning。
  - 验收：人为慢查询触发日志。

## 依赖

- [auth.md](./auth.md)：users/api_keys 的消费者。
- [api-external.md](./api-external.md)：audit_logs 的写入者。
- [tests.md](./tests.md)：用 `pytest-postgresql` / testcontainers 起隔离实例。

## 参考

- spec §5.1 docker-compose；§3 数据建模选择（图 vs 关系）。
- 设计方案 §6（持久化分层）。

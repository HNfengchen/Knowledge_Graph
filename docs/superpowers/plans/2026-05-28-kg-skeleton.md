# 知识图谱系统骨架 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 `docs/superpowers/specs/2026-05-28-kg-skeleton-design.md` 落地全栈骨架；`docker compose up` 后 `POST /api/v1/kg/build` 与 `POST /api/v1/kg/query` 端到端可跑，其余端点 501。

**Architecture:** Python 3.11 + FastAPI + LangChain/LangGraph + 异步 Neo4j 驱动 + Redis 异步连接池。`pyproject.toml` + `src/` 布局，按业务能力分模块（api / builder / reasoning / llm / analysis / storage / kg_query / core）。模块依赖单向：`api → 业务模块 → llm/storage → core`。

**Tech Stack:** fastapi, uvicorn, pydantic v2, pydantic-settings, langchain 0.3, langgraph, neo4j async driver, redis async, structlog, python-jose, httpx, d3 v7。

**任务总览：** 共 23 个任务，按依赖顺序执行：

```
T01-T03  基建（pyproject, .gitignore, Dockerfile + .dockerignore）
T04      core/config
T05      core/exceptions + core/models + core/logging
T06-T07  storage（neo4j_client, redis_client, schemas）
T08      llm/factory + llm/cache + llm/callbacks
T09-T11  builder（chunker, extractor, disambiguator, pipeline）
T12      kg_query/service
T13      reasoning/state + nodes + graph（占位）
T14      analysis/collector + metrics + alerts（占位）
T15-T18  api（deps, middleware, v1/kg, v1/reason+analysis+external）
T19      main.py（lifespan + app 装配）
T20      __main__.py
T21      docker-compose.yml
T22      prompts/*.txt
T23      frontend/graphpanel.vue + README + 顶层 README
```

**TDD 取舍：** 用户选「骨架阶段不写测试」，因此本计划以**导入冒烟**与**`docker compose up` + curl 端到端验证**作为每任务的验证手段。每任务有明确的"验证命令 + 预期输出"。

**提交粒度：** 每任务一次 commit。仓库当前**非 git 仓库**（环境标注 `Is a git repository: false` —— 注：环境提示存在不一致，T01 起首先 `git init`，后续每任务 commit）。

---

## File Structure

新建文件清单（按任务顺序）：

```
pyproject.toml                                  T01
.gitignore (修改)                                T01
Dockerfile                                       T03
.dockerignore                                    T03
src/kg_system/__init__.py                        T04
src/kg_system/core/__init__.py                   T04
src/kg_system/core/config.py                     T04
src/kg_system/core/exceptions.py                 T05
src/kg_system/core/models.py                     T05
src/kg_system/core/logging.py                    T05
src/kg_system/storage/__init__.py                T06
src/kg_system/storage/neo4j_client.py            T06
src/kg_system/storage/redis_client.py            T07
src/kg_system/storage/schemas.py                 T07
src/kg_system/llm/__init__.py                    T08
src/kg_system/llm/factory.py                     T08
src/kg_system/llm/cache.py                       T08
src/kg_system/llm/callbacks.py                   T08
src/kg_system/builder/__init__.py                T09
src/kg_system/builder/chunker.py                 T09
src/kg_system/builder/extractor.py               T10
src/kg_system/builder/disambiguator.py           T11
src/kg_system/builder/pipeline.py                T11
src/kg_system/kg_query/__init__.py               T12
src/kg_system/kg_query/service.py                T12
src/kg_system/reasoning/__init__.py              T13
src/kg_system/reasoning/state.py                 T13
src/kg_system/reasoning/nodes.py                 T13
src/kg_system/reasoning/graph.py                 T13
src/kg_system/analysis/__init__.py               T14
src/kg_system/analysis/collector.py              T14
src/kg_system/analysis/metrics.py                T14
src/kg_system/analysis/alerts.py                 T14
src/kg_system/api/__init__.py                    T15
src/kg_system/api/deps.py                        T15
src/kg_system/api/middleware.py                  T16
src/kg_system/api/v1/__init__.py                 T17
src/kg_system/api/v1/kg.py                       T17
src/kg_system/api/v1/reason.py                   T18
src/kg_system/api/v1/analysis.py                 T18
src/kg_system/api/v1/external.py                 T18
src/kg_system/main.py                            T19
src/kg_system/__main__.py                        T20
docker-compose.yml                               T21
prompts/entity_extraction.txt                    T22
prompts/relation_extraction.txt                  T22
frontend/graphpanel.vue                          T23
frontend/README.md                               T23
README.md                                        T23
```

---

### Task 01: 项目基建 — `pyproject.toml` + git init + `.gitignore`

**Files:**
- Create: `pyproject.toml`
- Modify: `.gitignore`（追加 Python 项目排除项）

- [ ] **Step 1: 初始化 git**

```bash
git init
git checkout -b master 2>/dev/null || true
```

预期：`Initialized empty Git repository in .../Knowledge_Graph/.git/`（若已存在则忽略）。

- [ ] **Step 2: 写 `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "kg-system"
version = "0.1.0"
description = "LLM-driven knowledge graph construction & analysis system (skeleton)"
requires-python = ">=3.11"
readme = "README.md"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
    "pydantic-settings>=2.6",
    "python-dotenv>=1.0",
    "langchain>=0.3",
    "langchain-core>=0.3",
    "langchain-openai>=0.2",
    "langchain-anthropic>=0.2",
    "langgraph>=0.2",
    "neo4j>=5.25",
    "redis[hiredis]>=5.2",
    "httpx>=0.27",
    "structlog>=24.4",
    "python-jose[cryptography]>=3.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "ruff>=0.7",
    "mypy>=1.13",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"kg_system" = ["py.typed"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: 追加 `.gitignore`**

确认 `.gitignore` 至少包含以下条目（已存在的不重复添加）：

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
*.egg
.eggs/
build/
dist/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Env
.env

# IDE
.vscode/
.idea/

# Codegraph
.codegraph/

# Docker volumes (本地)
neo4j_data/
redis_data/
postgres_data/
```

- [ ] **Step 4: 验证可安装**

```bash
pip install -e ".[dev]"
```

预期：所有依赖装好，无 `error:`。最后一行类似 `Successfully installed kg-system-0.1.0 ...`。

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: bootstrap pyproject + gitignore"
```

---

### Task 02: 占位包目录（让 `pip install -e` 真正能找到包）

**Files:**
- Create: `src/kg_system/__init__.py`

- [ ] **Step 1: 写 `src/kg_system/__init__.py`**

```python
"""kg_system — LLM-driven knowledge graph system (skeleton)."""

__version__ = "0.1.0"
```

- [ ] **Step 2: 验证导入**

```bash
python -c "import kg_system; print(kg_system.__version__)"
```

预期：`0.1.0`

- [ ] **Step 3: 提交**

```bash
git add src/kg_system/__init__.py
git commit -m "chore: add kg_system package init"
```

---

### Task 03: `Dockerfile` + `.dockerignore`

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: 写 `Dockerfile`**

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e ".[dev]"

COPY prompts ./prompts

EXPOSE 8000

CMD ["uvicorn", "kg_system.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 写 `.dockerignore`**

```
# 排除非运行时文件，缩小镜像
.git/
.gitignore
.venv/
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.pytest_cache/
.mypy_cache/
.ruff_cache/
.codegraph/

# 文档与前端
docs/
frontend/
*.md

# 本地配置
.env
.env.local

# IDE
.vscode/
.idea/

# Compose volume 数据
neo4j_data/
redis_data/
postgres_data/
```

- [ ] **Step 3: 提交**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add Dockerfile + dockerignore"
```

注：T03 结束时 `prompts/` 目录还不存在，`Dockerfile` 中的 `COPY prompts ./prompts` 会在 T22 创建后才能 build 成功。骨架阶段先不要求 build 通，T22 完成后再回来 build 验证（见 T22 验证步骤）。

---

### Task 04: `core/config.py` — 配置加载

**Files:**
- Create: `src/kg_system/core/__init__.py`
- Create: `src/kg_system/core/config.py`

依赖 `.env.example` 的全部键名，`pydantic-settings` 自动从环境变量读取。

- [ ] **Step 1: 写 `src/kg_system/core/__init__.py`**

```python
"""核心共享层：配置、异常、日志、领域模型。"""
```

- [ ] **Step 2: 写 `src/kg_system/core/config.py`**

```python
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全部环境配置。字段名与 .env.example 的键一一对应。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 应用基础
    APP_NAME: str = "knowledge-graph-system"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # LLM
    LLM_DEFAULT_PROVIDER: Literal["openai", "anthropic", "local"] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TIMEOUT: int = 60
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_TEMPERATURE: float = 0.7
    ANTHROPIC_MAX_TOKENS: int = 4096
    LOCAL_LLM_BASE_URL: str = "http://localhost:8000/v1"
    LOCAL_LLM_MODEL: str = "qwen2.5-7b-instruct"
    LOCAL_LLM_API_KEY: str = "not-needed"
    LOCAL_LLM_TEMPERATURE: float = 0.7
    LOCAL_LLM_MAX_TOKENS: int = 4096

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50
    NEO4J_CONNECTION_TIMEOUT: int = 30

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_SSL: bool = False
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_KEY_PREFIX: str = "kg:"
    REDIS_CACHE_TTL: int = 3600
    REDIS_STREAM_KEY: str = "llm_calls_stream"
    REDIS_METRICS_PREFIX: str = "metrics:"

    # Postgres（骨架未使用）
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "kg_user"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DATABASE: str = "knowledge_graph"
    POSTGRES_POOL_SIZE: int = 10

    # 安全
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    API_KEY_PREFIX: str = "kg-api-"
    API_KEY_HEADER: str = "X-API-Key"
    ADMIN_TOKEN: str = ""
    EXTERNAL_API_KEY: str = ""
    EXTERNAL_API_IP_WHITELIST: str = "127.0.0.1,::1"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Content-Type,Authorization,X-API-Key"

    # 构建
    TEXT_CHUNK_SIZE: int = 1000
    TEXT_CHUNK_OVERLAP: int = 200
    TEXT_MAX_LENGTH: int = 10000
    ENTITY_EXTRACTION_PROMPT_TEMPLATES: str = "/app/prompts/entity_extraction.txt"
    ENTITY_TYPES: str = "Person,Organization,Location,Event,Concept"
    ENTITY_SIMILARITY_THRESHOLD: float = 0.85
    RELATION_EXTRACTION_PROMPT_TEMPLATES: str = "/app/prompts/relation_extraction.txt"
    RELATION_TYPES: str = "RELATED_TO,HAS_PROPERTY,PART_OF,WORKS_FOR,LOCATED_IN"
    RELATION_SIMILARITY_THRESHOLD: float = 0.80
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_BATCH_SIZE: int = 100

    # 推理
    REASONING_MAX_STEPS: int = 5
    REASONING_SUBGRAPH_DEPTH: int = 3
    REASONING_SUBGRAPH_MAX_NODES: int = 100
    REASONING_TEMPERATURE: float = 0.3

    # 告警
    ALERT_ENABLED: bool = True
    ALERT_CHECK_INTERVAL: int = 60
    ALERT_QPS_THRESHOLD: int = 500
    ALERT_AVG_RESPONSE_TIME_THRESHOLD: int = 5000
    ALERT_P99_RESPONSE_TIME_THRESHOLD: int = 10000
    ALERT_ERROR_RATE_THRESHOLD: float = 0.01
    ALERT_SUCCESS_RATE_THRESHOLD: float = 0.99
    ALERT_LOG_ENABLED: bool = True
    ALERT_WEBHOOK_URL: str = ""
    ALERT_WEBHOOK_TIMEOUT: int = 10
    ALERT_EMAIL_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    ALERT_EMAIL_RECIPIENTS: str = ""

    # 成本
    COST_OPENAI_GPT4O_INPUT: float = 2.50
    COST_OPENAI_GPT4O_OUTPUT: float = 10.00
    COST_OPENAI_GPT4O_MINI_INPUT: float = 0.15
    COST_OPENAI_GPT4O_MINI_OUTPUT: float = 0.60
    COST_ANTHROPIC_CLAUDE35_INPUT: float = 3.00
    COST_ANTHROPIC_CLAUDE35_OUTPUT: float = 15.00
    COST_LOCAL_MODEL_INPUT: float = 0.00
    COST_LOCAL_MODEL_OUTPUT: float = 0.00
    DAILY_BUDGET_USD: float = 100.00
    MONTHLY_BUDGET_USD: float = 2000.00
    BUDGET_ALERT_THRESHOLD: float = 0.80

    # 缓存
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.95
    SEMANTIC_CACHE_MAX_SIZE: int = 10000
    SEMANTIC_CACHE_TTL: int = 86400

    # 前端
    FRONTEND_API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_WS_URL: str = "ws://localhost:8000"
    FRONTEND_DEFAULT_GRAPH_DEPTH: int = 2
    FRONTEND_MAX_GRAPH_NODES: int = 500

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    LOG_FILE_ENABLED: bool = False
    LOG_FILE_PATH: str = "/var/log/kg/app.log"
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 5

    # 性能
    HTTP_CONNECTION_POOL_SIZE: int = 100
    HTTP_CONNECTION_TIMEOUT: int = 30
    ASYNC_WORKER_COUNT: int = 4
    ASYNC_TASK_TIMEOUT: int = 300
    CACHE_WARMUP_ENABLED: bool = False
    CACHE_WARMUP_ENTITIES: str = "high_priority_entities.txt"

    # —— 派生属性 ——
    @property
    def entity_types_list(self) -> list[str]:
        return [t.strip() for t in self.ENTITY_TYPES.split(",") if t.strip()]

    @property
    def relation_types_list(self) -> list[str]:
        return [t.strip() for t in self.RELATION_TYPES.split(",") if t.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def external_ip_whitelist(self) -> set[str]:
        return {ip.strip() for ip in self.EXTERNAL_API_IP_WHITELIST.split(",") if ip.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 3: 验证加载**

```bash
python -c "from kg_system.core.config import get_settings; s = get_settings(); print(s.APP_NAME, s.LLM_DEFAULT_PROVIDER, s.entity_types_list)"
```

预期：`knowledge-graph-system openai ['Person', 'Organization', 'Location', 'Event', 'Concept']`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/core/__init__.py src/kg_system/core/config.py
git commit -m "feat(core): add Settings via pydantic-settings"
```

---

### Task 05: `core/exceptions.py` + `core/models.py` + `core/logging.py`

**Files:**
- Create: `src/kg_system/core/exceptions.py`
- Create: `src/kg_system/core/models.py`
- Create: `src/kg_system/core/logging.py`

- [ ] **Step 1: 写 `exceptions.py`**

```python
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
```

- [ ] **Step 2: 写 `models.py`**

```python
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


# —— 抽取阶段中间表示 ——
class ExtractedEntity(BaseModel):
    name: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    source_chunk_id: str | None = None


class ExtractedRelation(BaseModel):
    head: str
    tail: str
    relation: str
    props: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


# —— 出库后给前端的图结构 ——
class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphLink(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0


class SubgraphResult(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)


# —— HTTP 包装 ——
T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    msg: str = "success"
    data: T | None = None


# —— 告警 ——
class Alert(BaseModel):
    rule: str
    severity: str
    message: str
    metrics: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 3: 写 `logging.py`**

```python
from __future__ import annotations

import logging
import sys

import structlog

from kg_system.core.config import get_settings


def configure_logging() -> None:
    """根据 settings.LOG_FORMAT 装配 structlog 与标准 logging。幂等。"""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if settings.LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 4: 验证导入**

```bash
python -c "from kg_system.core.exceptions import KGException, NotImplementedInSkeleton; from kg_system.core.models import ApiResponse, SubgraphResult; from kg_system.core.logging import configure_logging, get_logger; configure_logging(); get_logger('test').info('hello', k='v'); print('ok')"
```

预期：输出一行 JSON 日志，最后打印 `ok`。

- [ ] **Step 5: 提交**

```bash
git add src/kg_system/core/exceptions.py src/kg_system/core/models.py src/kg_system/core/logging.py
git commit -m "feat(core): exceptions, domain models, structlog config"
```

---

### Task 06: `storage/neo4j_client.py` — 异步 Neo4j 驱动 + 核心 Cypher

**Files:**
- Create: `src/kg_system/storage/__init__.py`
- Create: `src/kg_system/storage/neo4j_client.py`

- [ ] **Step 1: 写 `src/kg_system/storage/__init__.py`**

```python
"""持久层：Neo4j、Redis、schema 初始化。"""
```

- [ ] **Step 2: 写 `src/kg_system/storage/neo4j_client.py`**

```python
from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from kg_system.core.config import get_settings
from kg_system.core.exceptions import Neo4jError
from kg_system.core.logging import get_logger
from kg_system.core.models import (
    ExtractedEntity,
    ExtractedRelation,
    GraphLink,
    GraphNode,
    SubgraphResult,
)

log = get_logger(__name__)


class Neo4jClient:
    """异步 Neo4j 客户端。封装 upsert / 子图查询 / 任意 Cypher 执行。"""

    def __init__(self, driver: AsyncDriver, database: str) -> None:
        self._driver = driver
        self._database = database

    @classmethod
    async def create(cls) -> "Neo4jClient":
        s = get_settings()
        driver = AsyncGraphDatabase.driver(
            s.NEO4J_URI,
            auth=(s.NEO4J_USER, s.NEO4J_PASSWORD),
            max_connection_pool_size=s.NEO4J_MAX_CONNECTION_POOL_SIZE,
            connection_timeout=s.NEO4J_CONNECTION_TIMEOUT,
        )
        try:
            await driver.verify_connectivity()
        except Exception as e:
            await driver.close()
            raise Neo4jError(f"failed to connect Neo4j: {e}") from e
        log.info("neo4j_connected", uri=s.NEO4J_URI, database=s.NEO4J_DATABASE)
        return cls(driver, s.NEO4J_DATABASE)

    async def close(self) -> None:
        await self._driver.close()

    async def execute_cypher(self, cypher: str, params: dict | None = None) -> list[dict]:
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def find_entity_by_name(self, name: str, type: str | None = None) -> GraphNode | None:
        if type:
            cypher = "MATCH (e:Entity {name:$name, type:$type}) RETURN e LIMIT 1"
            params = {"name": name, "type": type}
        else:
            cypher = "MATCH (e:Entity {name:$name}) RETURN e LIMIT 1"
            params = {"name": name}
        rows = await self.execute_cypher(cypher, params)
        if not rows:
            return None
        e = rows[0]["e"]
        return GraphNode(
            id=e.get("id"),
            name=e.get("name"),
            type=e.get("type"),
            props={k: v for k, v in e.items() if k not in {"id", "name", "type", "embedding"}},
        )

    async def upsert_entities(self, entities: list[ExtractedEntity]) -> dict[str, str]:
        """对每个 entity 按 (name,type) merge；返回 name→uuid 映射。"""
        if not entities:
            return {}
        name_to_id: dict[str, str] = {}
        cypher = """
        MERGE (e:Entity {name:$name, type:$type})
        ON CREATE SET e.id=$id, e.created_at=timestamp()
        ON MATCH  SET e.updated_at=timestamp()
        SET e += $props
        RETURN e.id AS id
        """
        async with self._driver.session(database=self._database) as session:
            for ent in entities:
                eid = str(uuid.uuid4())
                params = {
                    "name": ent.name,
                    "type": ent.type,
                    "id": eid,
                    "props": ent.props,
                }
                result = await session.run(cypher, params)
                rec = await result.single()
                name_to_id[ent.name] = rec["id"] if rec else eid
        log.info("entities_upserted", count=len(name_to_id))
        return name_to_id

    async def upsert_relations(
        self,
        relations: list[ExtractedRelation],
        name_to_id: dict[str, str],
    ) -> int:
        """按头尾节点 id + relation_type merge 关系。返回新增/更新数。"""
        if not relations:
            return 0
        cypher = """
        MATCH (h:Entity {id:$head_id})
        MATCH (t:Entity {id:$tail_id})
        MERGE (h)-[r:RELATED_TO {relation_type:$rel}]->(t)
        ON CREATE SET r.id=$rid, r.weight=$weight, r.created_at=timestamp()
        ON MATCH  SET r.weight=$weight, r.updated_at=timestamp()
        SET r += $props
        RETURN r.id AS rid
        """
        count = 0
        async with self._driver.session(database=self._database) as session:
            for rel in relations:
                head_id = name_to_id.get(rel.head)
                tail_id = name_to_id.get(rel.tail)
                if not head_id or not tail_id:
                    continue
                params = {
                    "head_id": head_id,
                    "tail_id": tail_id,
                    "rel": rel.relation,
                    "rid": str(uuid.uuid4()),
                    "weight": rel.weight,
                    "props": rel.props,
                }
                await session.run(cypher, params)
                count += 1
        log.info("relations_upserted", count=count)
        return count

    async def match_subgraph(
        self,
        entity_name: str,
        depth: int,
        relation_types: list[str] | None = None,
    ) -> SubgraphResult:
        """返回以 entity_name 为中心、深度 depth 的子图，转 D3 friendly 结构。"""
        depth = max(1, min(depth, 3))
        if relation_types:
            where_rel = " AND ALL(rr IN relationships(p) WHERE rr.relation_type IN $rel_types)"
        else:
            where_rel = ""
        cypher = f"""
        MATCH p=(e:Entity {{name:$name}})-[r:RELATED_TO*1..{depth}]-(n:Entity)
        WHERE 1=1 {where_rel}
        WITH nodes(p) AS ns, relationships(p) AS rs
        UNWIND ns AS n
        WITH collect(DISTINCT n) AS nodes_all, rs
        UNWIND rs AS r
        WITH nodes_all, collect(DISTINCT r) AS rels_all
        RETURN nodes_all, rels_all
        """
        params: dict[str, Any] = {"name": entity_name}
        if relation_types:
            params["rel_types"] = relation_types
        rows = await self.execute_cypher(cypher, params)
        if not rows:
            return SubgraphResult()
        row = rows[0]
        nodes = [
            GraphNode(
                id=n.get("id"),
                name=n.get("name"),
                type=n.get("type"),
                props={
                    k: v
                    for k, v in n.items()
                    if k not in {"id", "name", "type", "embedding"}
                },
            )
            for n in row["nodes_all"]
        ]
        links: list[GraphLink] = []
        for r in row["rels_all"]:
            start_id = r.start_node.get("id") if hasattr(r, "start_node") else r.get("start_id")
            end_id = r.end_node.get("id") if hasattr(r, "end_node") else r.get("end_id")
            links.append(
                GraphLink(
                    source=start_id,
                    target=end_id,
                    relation=r.get("relation_type", "RELATED_TO"),
                    weight=r.get("weight", 1.0),
                )
            )
        return SubgraphResult(nodes=nodes, links=links)
```

注：`r.start_node` 在 neo4j-python-driver 5.x 的 `Relationship` 上可用。若未来驱动版本 API 变动，落到 `hasattr` 兜底分支。

- [ ] **Step 3: 验证导入**

```bash
python -c "from kg_system.storage.neo4j_client import Neo4jClient; print(Neo4jClient.__name__)"
```

预期：`Neo4jClient`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/storage/__init__.py src/kg_system/storage/neo4j_client.py
git commit -m "feat(storage): async Neo4jClient (upsert + subgraph)"
```

---

### Task 07: `storage/redis_client.py` + `storage/schemas.py`

**Files:**
- Create: `src/kg_system/storage/redis_client.py`
- Create: `src/kg_system/storage/schemas.py`

- [ ] **Step 1: 写 `redis_client.py`**

```python
from __future__ import annotations

from redis.asyncio import ConnectionPool, Redis

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger

log = get_logger(__name__)


class RedisClient:
    """异步 Redis 连接池封装。提供 get_client() 拿到 Redis 实例。"""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls) -> "RedisClient":
        s = get_settings()
        pool = ConnectionPool(
            host=s.REDIS_HOST,
            port=s.REDIS_PORT,
            password=s.REDIS_PASSWORD or None,
            db=s.REDIS_DB,
            ssl=s.REDIS_SSL,
            decode_responses=s.REDIS_DECODE_RESPONSES,
            max_connections=50,
        )
        client = Redis(connection_pool=pool)
        try:
            await client.ping()
        except Exception as e:
            await pool.disconnect()
            raise RuntimeError(f"failed to connect Redis: {e}") from e
        finally:
            await client.close()
        log.info("redis_connected", host=s.REDIS_HOST, port=s.REDIS_PORT, db=s.REDIS_DB)
        return cls(pool)

    def get_client(self) -> Redis:
        return Redis(connection_pool=self._pool)

    async def close(self) -> None:
        await self._pool.disconnect()
```

- [ ] **Step 2: 写 `schemas.py`**

```python
from __future__ import annotations

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT entity_name_type_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
]

FULLTEXT_INDEXES: list[str] = [
    "CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS "
    "FOR (e:Entity) ON EACH [e.name, e.description]",
]


def _vector_index_cypher(dim: int) -> str:
    return (
        "CREATE VECTOR INDEX entity_embedding IF NOT EXISTS "
        "FOR (e:Entity) ON e.embedding "
        "OPTIONS { indexConfig: { "
        f"`vector.dimensions`: {dim}, "
        "`vector.similarity_function`: 'cosine' "
        "} }"
    )


async def apply_schema(client: Neo4jClient) -> None:
    """启动时执行。所有语句幂等（IF NOT EXISTS）。"""
    s = get_settings()
    statements = [*CONSTRAINTS, *FULLTEXT_INDEXES, _vector_index_cypher(s.EMBEDDING_DIMENSIONS)]
    for stmt in statements:
        try:
            await client.execute_cypher(stmt)
            log.info("schema_applied", stmt=stmt[:80])
        except Exception as e:
            # 老版本 Neo4j 不支持 vector index 时给 warning，不阻塞启动
            log.warning("schema_stmt_failed", stmt=stmt[:80], error=str(e))
```

- [ ] **Step 3: 验证导入**

```bash
python -c "from kg_system.storage.redis_client import RedisClient; from kg_system.storage.schemas import apply_schema, CONSTRAINTS; print(len(CONSTRAINTS))"
```

预期：`2`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/storage/redis_client.py src/kg_system/storage/schemas.py
git commit -m "feat(storage): redis async pool + neo4j schema bootstrap"
```

---

### Task 08: `llm/factory.py` + `llm/cache.py` + `llm/callbacks.py`

**Files:**
- Create: `src/kg_system/llm/__init__.py`
- Create: `src/kg_system/llm/factory.py`
- Create: `src/kg_system/llm/cache.py`
- Create: `src/kg_system/llm/callbacks.py`

- [ ] **Step 1: 写 `src/kg_system/llm/__init__.py`**

```python
"""LLM 集成层：工厂、缓存、调用埋点。"""
```

- [ ] **Step 2: 写 `factory.py`**

```python
from __future__ import annotations

from typing import Literal

from langchain_core.language_models import BaseChatModel

from kg_system.core.config import get_settings
from kg_system.core.exceptions import ConfigError

Provider = Literal["openai", "anthropic", "local"]


def get_chat_model(provider: Provider | None = None) -> BaseChatModel:
    """provider=None 时使用 settings.LLM_DEFAULT_PROVIDER。"""
    s = get_settings()
    p: str = provider or s.LLM_DEFAULT_PROVIDER

    if p == "openai":
        from langchain_openai import ChatOpenAI

        if not s.OPENAI_API_KEY:
            raise ConfigError("OPENAI_API_KEY is empty")
        return ChatOpenAI(
            api_key=s.OPENAI_API_KEY,
            base_url=s.OPENAI_BASE_URL,
            model=s.OPENAI_MODEL,
            temperature=s.OPENAI_TEMPERATURE,
            max_tokens=s.OPENAI_MAX_TOKENS,
            timeout=s.OPENAI_TIMEOUT,
        )

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not s.ANTHROPIC_API_KEY:
            raise ConfigError("ANTHROPIC_API_KEY is empty")
        return ChatAnthropic(
            api_key=s.ANTHROPIC_API_KEY,
            base_url=s.ANTHROPIC_BASE_URL,
            model=s.ANTHROPIC_MODEL,
            temperature=s.ANTHROPIC_TEMPERATURE,
            max_tokens=s.ANTHROPIC_MAX_TOKENS,
        )

    if p == "local":
        # 走 OpenAI 兼容协议，base_url 指向本地 vLLM/Ollama
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=s.LOCAL_LLM_API_KEY,
            base_url=s.LOCAL_LLM_BASE_URL,
            model=s.LOCAL_LLM_MODEL,
            temperature=s.LOCAL_LLM_TEMPERATURE,
            max_tokens=s.LOCAL_LLM_MAX_TOKENS,
        )

    raise ConfigError(f"unknown LLM provider: {p}")
```

- [ ] **Step 3: 写 `cache.py`**

```python
from __future__ import annotations

from typing import Any

from kg_system.core.logging import get_logger

log = get_logger(__name__)


class SemanticCache:
    """语义缓存接口。骨架实现：直通（不缓存），以便后续替换为 embedding+向量检索。"""

    async def get(self, prompt: str) -> str | None:
        return None

    async def set(self, prompt: str, response: str, metadata: dict[str, Any] | None = None) -> None:
        # 占位：将来写入 Redis + 向量索引
        return None
```

- [ ] **Step 4: 写 `callbacks.py`**

```python
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
```

- [ ] **Step 5: 验证导入**

```bash
python -c "from kg_system.llm.factory import get_chat_model; from kg_system.llm.cache import SemanticCache; from kg_system.llm.callbacks import AnalysisCallbackHandler; print('ok')"
```

预期：`ok`

- [ ] **Step 6: 提交**

```bash
git add src/kg_system/llm
git commit -m "feat(llm): factory + semantic cache stub + analysis callback"
```

---

### Task 09: `builder/chunker.py` — 文本分块

**Files:**
- Create: `src/kg_system/builder/__init__.py`
- Create: `src/kg_system/builder/chunker.py`

- [ ] **Step 1: 写 `src/kg_system/builder/__init__.py`**

```python
"""KG 构建模块：分块、抽取、消歧、入库 pipeline。"""
```

- [ ] **Step 2: 写 `chunker.py`**

```python
from __future__ import annotations

from kg_system.core.config import get_settings


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """按字符长度滑窗分块。骨架阶段不做语义切分，避免引入 tiktoken/分词器。"""
    s = get_settings()
    cs = chunk_size if chunk_size is not None else s.TEXT_CHUNK_SIZE
    ov = overlap if overlap is not None else s.TEXT_CHUNK_OVERLAP
    if cs <= 0:
        raise ValueError("chunk_size must be > 0")
    if ov < 0 or ov >= cs:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    text = text.strip()
    if not text:
        return []
    if len(text) <= cs:
        return [text]

    chunks: list[str] = []
    step = cs - ov
    i = 0
    while i < len(text):
        chunks.append(text[i : i + cs])
        if i + cs >= len(text):
            break
        i += step
    return chunks
```

- [ ] **Step 3: 验证**

```bash
python -c "from kg_system.builder.chunker import chunk_text; print(len(chunk_text('a'*2500, 1000, 200)))"
```

预期：`3`（2500 字符按 1000/200 步长 800 → [0:1000], [800:1800], [1600:2500]）

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/builder/__init__.py src/kg_system/builder/chunker.py
git commit -m "feat(builder): char-window chunker"
```

---

### Task 10: `builder/extractor.py` — 实体/关系抽取

**Files:**
- Create: `src/kg_system/builder/extractor.py`

抽取流程：读 prompt 模板 → format 占位符 → 调 LLM → 解析返回 JSON → Pydantic 校验。

Prompt 模板路径解析顺序：
1. `settings.ENTITY_EXTRACTION_PROMPT_TEMPLATES` 指向的绝对路径（容器内为 `/app/prompts/...`）
2. 若文件不存在，fallback 到仓库相对路径 `prompts/entity_extraction.txt`

- [ ] **Step 1: 写 `extractor.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from kg_system.core.config import get_settings
from kg_system.core.exceptions import LLMError
from kg_system.core.logging import get_logger
from kg_system.core.models import ExtractedEntity, ExtractedRelation

log = get_logger(__name__)


class _EntitiesPayload(BaseModel):
    entities: list[ExtractedEntity]


class _RelationsPayload(BaseModel):
    relations: list[ExtractedRelation]


def _read_prompt(primary_path: str, fallback_relative: str) -> str:
    p = Path(primary_path)
    if p.is_file():
        return p.read_text(encoding="utf-8")
    fb = Path(fallback_relative)
    if fb.is_file():
        return fb.read_text(encoding="utf-8")
    raise FileNotFoundError(f"prompt not found: {primary_path} (fallback {fallback_relative})")


def _parse_json_strict(content: str) -> dict:
    """LLM 偶尔会包 markdown 代码块；剥掉再 json.loads。"""
    text = content.strip()
    if text.startswith("```"):
        # 去掉 ```json ... ``` / ``` ... ``` 包裹
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)


class EntityExtractor:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        s = get_settings()
        self._prompt_tpl = _read_prompt(
            s.ENTITY_EXTRACTION_PROMPT_TEMPLATES,
            "prompts/entity_extraction.txt",
        )
        self._entity_types = ",".join(s.entity_types_list)

    async def extract(self, chunk: str) -> list[ExtractedEntity]:
        prompt = self._prompt_tpl.format(text=chunk, entity_types=self._entity_types)
        try:
            msg = await self._llm.ainvoke([HumanMessage(content=prompt)])
        except Exception as e:
            raise LLMError(f"entity extraction LLM call failed: {e}") from e
        try:
            payload = _EntitiesPayload(**_parse_json_strict(str(msg.content)))
        except (json.JSONDecodeError, ValidationError) as e:
            log.warning("entity_parse_failed", error=str(e), raw=str(msg.content)[:200])
            return []
        return payload.entities


class RelationExtractor:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        s = get_settings()
        self._prompt_tpl = _read_prompt(
            s.RELATION_EXTRACTION_PROMPT_TEMPLATES,
            "prompts/relation_extraction.txt",
        )
        self._relation_types = ",".join(s.relation_types_list)

    async def extract(
        self, chunk: str, entities: list[ExtractedEntity]
    ) -> list[ExtractedRelation]:
        if not entities:
            return []
        entities_str = json.dumps(
            [{"name": e.name, "type": e.type} for e in entities], ensure_ascii=False
        )
        prompt = self._prompt_tpl.format(
            text=chunk,
            entities=entities_str,
            relation_types=self._relation_types,
        )
        try:
            msg = await self._llm.ainvoke([HumanMessage(content=prompt)])
        except Exception as e:
            raise LLMError(f"relation extraction LLM call failed: {e}") from e
        try:
            payload = _RelationsPayload(**_parse_json_strict(str(msg.content)))
        except (json.JSONDecodeError, ValidationError) as e:
            log.warning("relation_parse_failed", error=str(e), raw=str(msg.content)[:200])
            return []
        valid_names = {e.name for e in entities}
        return [r for r in payload.relations if r.head in valid_names and r.tail in valid_names]
```

- [ ] **Step 2: 验证导入（暂不能调 LLM，只确认 import 通）**

```bash
python -c "from kg_system.builder.extractor import EntityExtractor, RelationExtractor; print('ok')"
```

预期：`ok`

- [ ] **Step 3: 提交**

```bash
git add src/kg_system/builder/extractor.py
git commit -m "feat(builder): entity & relation extractor (LLM + Pydantic)"
```

---

### Task 11: `builder/disambiguator.py` + `builder/pipeline.py`

**Files:**
- Create: `src/kg_system/builder/disambiguator.py`
- Create: `src/kg_system/builder/pipeline.py`

- [ ] **Step 1: 写 `disambiguator.py`**

```python
from __future__ import annotations

from kg_system.core.logging import get_logger
from kg_system.core.models import ExtractedEntity
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


class Disambiguator:
    """实体消歧。骨架阶段：按 (name, type) 完全匹配查现有节点，命中则带回原 props。
    后续可扩展为 fulltext 模糊匹配 + 向量相似度阈值。
    """

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def resolve(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        out: list[ExtractedEntity] = []
        for ent in entities:
            existing = await self._neo4j.find_entity_by_name(ent.name, ent.type)
            if existing is None:
                out.append(ent)
                continue
            merged_props = {**existing.props, **ent.props}
            out.append(
                ExtractedEntity(
                    name=ent.name,
                    type=ent.type,
                    props=merged_props,
                    source_chunk_id=ent.source_chunk_id,
                )
            )
        log.info("disambiguator_resolved", input=len(entities), output=len(out))
        return out
```

- [ ] **Step 2: 写 `pipeline.py`**

```python
from __future__ import annotations

import uuid

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from kg_system.builder.chunker import chunk_text
from kg_system.builder.disambiguator import Disambiguator
from kg_system.builder.extractor import EntityExtractor, RelationExtractor
from kg_system.core.logging import get_logger
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


class BuildResult(BaseModel):
    doc_id: str
    chunks: int
    entities_upserted: int
    relations_upserted: int


class KGBuildPipeline:
    """文本 → 分块 → 实体 → 关系 → 消歧 → 入库。"""

    def __init__(self, llm: BaseChatModel, neo4j: Neo4jClient) -> None:
        self._llm = llm
        self._neo4j = neo4j
        self._entity_ex = EntityExtractor(llm)
        self._relation_ex = RelationExtractor(llm)
        self._disamb = Disambiguator(neo4j)

    async def run(self, text: str, doc_id: str) -> BuildResult:
        chunks = chunk_text(text)
        log.info("pipeline_chunked", doc_id=doc_id, chunks=len(chunks))

        all_entities = []
        all_relations = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}::chunk-{idx}"
            ents = await self._entity_ex.extract(chunk)
            for e in ents:
                e.source_chunk_id = chunk_id
            rels = await self._relation_ex.extract(chunk, ents)
            all_entities.extend(ents)
            all_relations.extend(rels)

        resolved = await self._disamb.resolve(all_entities)
        name_to_id = await self._neo4j.upsert_entities(resolved)
        rel_count = await self._neo4j.upsert_relations(all_relations, name_to_id)

        return BuildResult(
            doc_id=doc_id,
            chunks=len(chunks),
            entities_upserted=len(name_to_id),
            relations_upserted=rel_count,
        )

    @staticmethod
    def gen_doc_id() -> str:
        return f"doc-{uuid.uuid4().hex[:12]}"
```

- [ ] **Step 3: 验证导入**

```bash
python -c "from kg_system.builder.pipeline import KGBuildPipeline, BuildResult; from kg_system.builder.disambiguator import Disambiguator; print('ok')"
```

预期：`ok`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/builder/disambiguator.py src/kg_system/builder/pipeline.py
git commit -m "feat(builder): disambiguator + KGBuildPipeline"
```

---

### Task 12: `kg_query/service.py` — 查询服务

**Files:**
- Create: `src/kg_system/kg_query/__init__.py`
- Create: `src/kg_system/kg_query/service.py`

- [ ] **Step 1: 写 `src/kg_system/kg_query/__init__.py`**

```python
"""对外查询服务：子图 / 实体上下文。"""
```

- [ ] **Step 2: 写 `service.py`**

```python
from __future__ import annotations

from kg_system.core.logging import get_logger
from kg_system.core.models import SubgraphResult
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


class KGQueryService:
    """业务侧/外部 LLM 调用图谱的统一入口。"""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def query_subgraph(
        self,
        entity_name: str,
        depth: int = 2,
        relation_types: list[str] | None = None,
    ) -> SubgraphResult:
        return await self._neo4j.match_subgraph(entity_name, depth, relation_types)

    async def get_entity_context(self, entity_name: str, max_neighbors: int = 10) -> str:
        """以 1-hop 邻居拼出文本上下文。骨架实现：简单字符串拼接。"""
        sg = await self._neo4j.match_subgraph(entity_name, depth=1)
        if not sg.nodes:
            return f"未找到实体 {entity_name}。"
        center = next((n for n in sg.nodes if n.name == entity_name), sg.nodes[0])
        lines = [f"实体: {center.name} (类型: {center.type})"]
        if center.props:
            lines.append(f"属性: {center.props}")
        neighbors = [n for n in sg.nodes if n.id != center.id][:max_neighbors]
        if neighbors:
            lines.append("相关实体:")
            for n in neighbors:
                rel = next(
                    (
                        l
                        for l in sg.links
                        if (l.source == center.id and l.target == n.id)
                        or (l.target == center.id and l.source == n.id)
                    ),
                    None,
                )
                rel_label = rel.relation if rel else "RELATED_TO"
                lines.append(f"  - [{rel_label}] {n.name} ({n.type})")
        return "\n".join(lines)
```

- [ ] **Step 3: 验证导入**

```bash
python -c "from kg_system.kg_query.service import KGQueryService; print('ok')"
```

预期：`ok`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/kg_query
git commit -m "feat(kg-query): subgraph + entity context service"
```

---

### Task 13: `reasoning/{state,nodes,graph}.py` — LangGraph 推理（占位）

**Files:**
- Create: `src/kg_system/reasoning/__init__.py`
- Create: `src/kg_system/reasoning/state.py`
- Create: `src/kg_system/reasoning/nodes.py`
- Create: `src/kg_system/reasoning/graph.py`

骨架阶段：StateGraph 装配代码完整、节点函数 `raise NotImplementedInSkeleton`。

- [ ] **Step 1: 写 `src/kg_system/reasoning/__init__.py`**

```python
"""LangGraph 推理模块（骨架占位）。"""
```

- [ ] **Step 2: 写 `state.py`**

```python
from __future__ import annotations

from typing import TypedDict


class ReasonerState(TypedDict, total=False):
    question: str
    subgraph: str
    reasoning_trace: list[str]
    answer: str
    next_action: str  # retrieve | reason | generate | end
    step_count: int
```

- [ ] **Step 3: 写 `nodes.py`**

```python
from __future__ import annotations

from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.reasoning.state import ReasonerState


async def retrieve_node(state: ReasonerState) -> ReasonerState:
    """根据 question 检索 Neo4j 子图。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.retrieve_node")


async def reason_node(state: ReasonerState) -> ReasonerState:
    """LLM 基于 subgraph + question 推理一步。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.reason_node")


async def decide_node(state: ReasonerState) -> ReasonerState:
    """判断是否需要再检索 / 已可生成答案。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.decide_node")


async def generate_node(state: ReasonerState) -> ReasonerState:
    """生成最终答案。骨架占位。"""
    raise NotImplementedInSkeleton("reasoning.generate_node")


def route_after_decide(state: ReasonerState) -> str:
    """conditional_edges 路由函数。骨架占位。"""
    return state.get("next_action", "end")
```

- [ ] **Step 4: 写 `graph.py`**

```python
from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from kg_system.reasoning.nodes import (
    decide_node,
    generate_node,
    reason_node,
    retrieve_node,
    route_after_decide,
)
from kg_system.reasoning.state import ReasonerState


def build_reasoning_graph() -> CompiledStateGraph:
    """装配 StateGraph 并 compile。节点函数本身在骨架内会 raise。"""
    workflow: StateGraph = StateGraph(ReasonerState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("reason", reason_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("generate", generate_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "reason")
    workflow.add_edge("reason", "decide")
    workflow.add_conditional_edges(
        "decide",
        route_after_decide,
        {
            "retrieve": "retrieve",
            "reason": "reason",
            "generate": "generate",
            "end": END,
        },
    )
    workflow.add_edge("generate", END)
    return workflow.compile()
```

- [ ] **Step 5: 验证装配**

```bash
python -c "from kg_system.reasoning.graph import build_reasoning_graph; g = build_reasoning_graph(); print(type(g).__name__)"
```

预期：`CompiledStateGraph`（具体类名以 langgraph 当前版本为准；不是异常即通）

- [ ] **Step 6: 提交**

```bash
git add src/kg_system/reasoning
git commit -m "feat(reasoning): LangGraph skeleton (state + nodes stubs + compiled graph)"
```

---

### Task 14: `analysis/{collector,metrics,alerts}.py` —— 调用分析（占位）

**Files:**
- Create: `src/kg_system/analysis/__init__.py`
- Create: `src/kg_system/analysis/collector.py`
- Create: `src/kg_system/analysis/metrics.py`
- Create: `src/kg_system/analysis/alerts.py`

- [ ] **Step 1: 写 `src/kg_system/analysis/__init__.py`**

```python
"""调用分析与告警（骨架占位）。"""
```

- [ ] **Step 2: 写 `collector.py`**

```python
from __future__ import annotations

import asyncio

from kg_system.core.logging import get_logger
from kg_system.storage.redis_client import RedisClient

log = get_logger(__name__)


class StreamCollector:
    """从 Redis Stream 消费 llm_calls_stream，写入 metrics。骨架阶段不消费数据，仅占位 task。"""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run(), name="stream-collector")
        log.info("stream_collector_started")

    async def _run(self) -> None:
        try:
            await self._stop.wait()
        except asyncio.CancelledError:
            return

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        log.info("stream_collector_stopped")
```

- [ ] **Step 3: 写 `metrics.py`**

```python
from __future__ import annotations

from kg_system.core.exceptions import NotImplementedInSkeleton


class MetricsAggregator:
    """QPS / 延迟分布 / 成本聚合。骨架占位。"""

    async def get_qps(self, window_seconds: int) -> float:
        raise NotImplementedInSkeleton("metrics.get_qps")

    async def get_latency_percentiles(self, window_seconds: int) -> dict[str, float]:
        raise NotImplementedInSkeleton("metrics.get_latency_percentiles")

    async def get_daily_cost_usd(self) -> float:
        raise NotImplementedInSkeleton("metrics.get_daily_cost_usd")
```

- [ ] **Step 4: 写 `alerts.py`**

```python
from __future__ import annotations

from typing import Any

from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import Alert


class AlertManager:
    ALERT_RULES: dict[str, dict[str, Any]] = {
        "error_rate_high": {
            "condition": "error_rate > 0.05",
            "severity": "warning",
            "channels": ["log", "webhook"],
        },
        "response_time_slow": {
            "condition": "p99_duration > 10000",
            "severity": "warning",
            "channels": ["log", "webhook"],
        },
        "cost_over_budget": {
            "condition": "daily_cost > budget_limit",
            "severity": "critical",
            "channels": ["log", "webhook", "email"],
        },
        "service_down": {
            "condition": "success_rate < 0.5",
            "severity": "critical",
            "channels": ["log", "webhook", "email", "sms"],
        },
    }

    async def evaluate(self, metrics: dict[str, Any]) -> list[Alert]:
        raise NotImplementedInSkeleton("AlertManager.evaluate")

    async def notify(self, alert: Alert) -> None:
        raise NotImplementedInSkeleton("AlertManager.notify")
```

- [ ] **Step 5: 验证导入**

```bash
python -c "from kg_system.analysis.collector import StreamCollector; from kg_system.analysis.metrics import MetricsAggregator; from kg_system.analysis.alerts import AlertManager; print(list(AlertManager.ALERT_RULES.keys()))"
```

预期：`['error_rate_high', 'response_time_slow', 'cost_over_budget', 'service_down']`

- [ ] **Step 6: 提交**

```bash
git add src/kg_system/analysis
git commit -m "feat(analysis): stream collector + metrics + alert manager skeleton"
```

---

### Task 15: `api/__init__.py` + `api/deps.py` —— 依赖注入

**Files:**
- Create: `src/kg_system/api/__init__.py`
- Create: `src/kg_system/api/deps.py`

约定：FastAPI app 在 `lifespan` 内创建 `Neo4jClient` / `RedisClient` 单例存到 `app.state.*`。`deps.py` 通过 `Request` 拿到 `app.state` 注入。

- [ ] **Step 1: 写 `src/kg_system/api/__init__.py`**

```python
"""HTTP 接入层：依赖注入、中间件、路由。"""
```

- [ ] **Step 2: 写 `deps.py`**

```python
from __future__ import annotations

from fastapi import Depends, Header, Request

from kg_system.core.config import get_settings
from kg_system.core.exceptions import AuthError
from kg_system.kg_query.service import KGQueryService
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.redis_client import RedisClient


# —— 资源依赖 —— #
def get_neo4j(request: Request) -> Neo4jClient:
    return request.app.state.neo4j


def get_redis(request: Request) -> RedisClient:
    return request.app.state.redis


def get_kg_query(neo4j: Neo4jClient = Depends(get_neo4j)) -> KGQueryService:
    return KGQueryService(neo4j)


# —— 认证依赖 —— #
def require_user(authorization: str | None = Header(default=None)) -> dict:
    """业务端点：Bearer JWT。骨架阶段只校验 token 非空 + 签名。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    token = authorization.split(None, 1)[1].strip()
    if not token:
        raise AuthError("empty bearer token")
    s = get_settings()
    try:
        from jose import jwt

        payload = jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    except Exception as e:
        raise AuthError(f"invalid token: {e}") from e
    return payload


def require_admin(authorization: str | None = Header(default=None)) -> None:
    """管理端点：admin token 直接比对 settings.ADMIN_TOKEN。"""
    s = get_settings()
    if not s.ADMIN_TOKEN:
        raise AuthError("admin token not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing admin bearer token")
    token = authorization.split(None, 1)[1].strip()
    if token != s.ADMIN_TOKEN:
        raise AuthError("invalid admin token")


def require_external(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """外部接口：API Key + IP 白名单。"""
    s = get_settings()
    if not s.EXTERNAL_API_KEY:
        raise AuthError("external API key not configured")
    if x_api_key != s.EXTERNAL_API_KEY:
        raise AuthError("invalid external API key")
    client_host = request.client.host if request.client else ""
    if client_host not in s.external_ip_whitelist:
        raise AuthError(f"IP {client_host} not in whitelist")
```

- [ ] **Step 3: 验证导入**

```bash
python -c "from kg_system.api.deps import get_neo4j, require_user, require_admin, require_external; print('ok')"
```

预期：`ok`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/api/__init__.py src/kg_system/api/deps.py
git commit -m "feat(api): dependency providers + auth guards"
```

---

### Task 16: `api/middleware.py` —— 异常处理 + 统一响应

**Files:**
- Create: `src/kg_system/api/middleware.py`

- [ ] **Step 1: 写 `middleware.py`**

```python
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
```

- [ ] **Step 2: 验证导入**

```bash
python -c "from kg_system.api.middleware import install_middleware_and_handlers; print('ok')"
```

预期：`ok`

- [ ] **Step 3: 提交**

```bash
git add src/kg_system/api/middleware.py
git commit -m "feat(api): unified response envelope + exception handlers"
```

---

### Task 17: `api/v1/kg.py` —— `/kg/build` + `/kg/query`（核心端点）

**Files:**
- Create: `src/kg_system/api/v1/__init__.py`
- Create: `src/kg_system/api/v1/kg.py`

- [ ] **Step 1: 写 `src/kg_system/api/v1/__init__.py`**

```python
"""API v1 路由集合。"""
```

- [ ] **Step 2: 写 `kg.py`**

```python
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from kg_system.api.deps import get_kg_query, get_neo4j, get_redis, require_user
from kg_system.builder.pipeline import KGBuildPipeline
from kg_system.core.config import get_settings
from kg_system.core.models import ApiResponse, SubgraphResult
from kg_system.kg_query.service import KGQueryService
from kg_system.llm.callbacks import AnalysisCallbackHandler
from kg_system.llm.factory import get_chat_model
from kg_system.storage.neo4j_client import Neo4jClient
from kg_system.storage.redis_client import RedisClient

router = APIRouter(prefix="/kg", tags=["kg"])


class BuildRequest(BaseModel):
    text: str = Field(..., min_length=1)
    doc_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BuildResponseData(BaseModel):
    doc_id: str
    chunks: int
    entities_upserted: int
    relations_upserted: int


class QueryRequest(BaseModel):
    entity_name: str
    depth: int = Field(2, ge=1, le=3)
    relation_types: list[str] | None = None


@router.post("/build", response_model=ApiResponse[BuildResponseData])
async def build_endpoint(
    body: BuildRequest,
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    s = get_settings()
    if len(body.text) > s.TEXT_MAX_LENGTH:
        from kg_system.core.exceptions import InvalidInput

        raise InvalidInput(f"text exceeds TEXT_MAX_LENGTH={s.TEXT_MAX_LENGTH}")

    callback = AnalysisCallbackHandler(redis)
    llm = get_chat_model().with_config({"callbacks": [callback]})
    pipeline = KGBuildPipeline(llm=llm, neo4j=neo4j)
    doc_id = body.doc_id or KGBuildPipeline.gen_doc_id()
    result = await pipeline.run(body.text, doc_id)
    return ApiResponse(
        data=BuildResponseData(
            doc_id=result.doc_id,
            chunks=result.chunks,
            entities_upserted=result.entities_upserted,
            relations_upserted=result.relations_upserted,
        )
    )


@router.post("/query", response_model=ApiResponse[SubgraphResult])
async def query_endpoint(
    body: QueryRequest,
    kg: KGQueryService = Depends(get_kg_query),
    user=Depends(require_user),
):
    sg = await kg.query_subgraph(body.entity_name, body.depth, body.relation_types)
    return ApiResponse(data=sg)
```

注：`/kg/query` 在前端 graphpanel.vue 中默认走 GET 也可以，骨架统一用 POST 携带 body。`api/v1/kg.py` 是核心端点；其他模块的 router 在 T18。

- [ ] **Step 3: 验证导入**

```bash
python -c "from kg_system.api.v1.kg import router; print(len(router.routes))"
```

预期：`2`

- [ ] **Step 4: 提交**

```bash
git add src/kg_system/api/v1/__init__.py src/kg_system/api/v1/kg.py
git commit -m "feat(api): /kg/build + /kg/query endpoints"
```

---

### Task 18: `api/v1/{reason,analysis,external}.py` —— 占位端点

**Files:**
- Create: `src/kg_system/api/v1/reason.py`
- Create: `src/kg_system/api/v1/analysis.py`
- Create: `src/kg_system/api/v1/external.py`

所有端点路由注册完整、Pydantic schema 定义完整、方法体 `raise NotImplementedInSkeleton`。

- [ ] **Step 1: 写 `reason.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kg_system.api.deps import require_user
from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import ApiResponse, SubgraphResult

router = APIRouter(prefix="/reason", tags=["reason"])


class AskRequest(BaseModel):
    question: str
    max_steps: int = Field(5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    reasoning_trace: list[str]
    evidence: SubgraphResult


@router.post("/ask", response_model=ApiResponse[AskResponse])
async def ask_endpoint(body: AskRequest, user=Depends(require_user)):
    raise NotImplementedInSkeleton("/reason/ask")
```

- [ ] **Step 2: 写 `analysis.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from kg_system.api.deps import require_admin
from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import ApiResponse

router = APIRouter(prefix="/llm", tags=["analysis"])


class AnalyzeData(BaseModel):
    qps: float
    avg_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    daily_cost_usd: float


@router.get("/analyze", response_model=ApiResponse[AnalyzeData])
async def analyze_endpoint(
    window_seconds: int = Query(300, ge=60, le=86400),
    _admin=Depends(require_admin),
):
    raise NotImplementedInSkeleton("/llm/analyze")
```

- [ ] **Step 3: 写 `external.py`**

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kg_system.api.deps import require_external
from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import ApiResponse, SubgraphResult

router = APIRouter(prefix="/kg/external", tags=["external"])


class SubgraphReq(BaseModel):
    entity_name: str
    depth: int = Field(2, ge=1, le=3)
    relation_types: list[str] | None = None


class ContextReq(BaseModel):
    entity_name: str
    max_neighbors: int = Field(10, ge=1, le=100)


class CypherReq(BaseModel):
    cypher: str
    params: dict = Field(default_factory=dict)


class EmbedReq(BaseModel):
    texts: list[str]


@router.post("/subgraph", response_model=ApiResponse[SubgraphResult])
async def subgraph_endpoint(body: SubgraphReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/subgraph")


@router.post("/context", response_model=ApiResponse[dict])
async def context_endpoint(body: ContextReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/context")


@router.post("/cypher", response_model=ApiResponse[list[dict]])
async def cypher_endpoint(body: CypherReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/cypher")


@router.post("/embed", response_model=ApiResponse[list[list[float]]])
async def embed_endpoint(body: EmbedReq, _ext=Depends(require_external)):
    raise NotImplementedInSkeleton("/kg/external/embed")
```

- [ ] **Step 4: 验证导入**

```bash
python -c "from kg_system.api.v1.reason import router as r1; from kg_system.api.v1.analysis import router as r2; from kg_system.api.v1.external import router as r3; print(len(r1.routes), len(r2.routes), len(r3.routes))"
```

预期：`1 1 4`

- [ ] **Step 5: 提交**

```bash
git add src/kg_system/api/v1/reason.py src/kg_system/api/v1/analysis.py src/kg_system/api/v1/external.py
git commit -m "feat(api): placeholder endpoints (reason/analysis/external) returning 501"
```

---

### Task 19: `main.py` —— FastAPI app 装配 + lifespan

**Files:**
- Create: `src/kg_system/main.py`

- [ ] **Step 1: 写 `main.py`**

```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kg_system.analysis.collector import StreamCollector
from kg_system.api.middleware import install_middleware_and_handlers
from kg_system.api.v1.analysis import router as analysis_router
from kg_system.api.v1.external import router as external_router
from kg_system.api.v1.kg import router as kg_router
from kg_system.api.v1.reason import router as reason_router
from kg_system.core.config import get_settings
from kg_system.core.logging import configure_logging, get_logger
from kg_system.core.models import ApiResponse
from kg_system.storage.neo4j_client import Neo4jClient
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

    log.info("startup_done")
    try:
        yield
    finally:
        log.info("shutdown_begin")
        await app.state.collector.stop()
        await app.state.redis.close()
        await app.state.neo4j.close()
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

    return app


app = create_app()
```

- [ ] **Step 2: 验证 app 装配**

```bash
python -c "from kg_system.main import app; print(app.title, len(app.routes))"
```

预期：`knowledge-graph-system N`，N ≥ 8（含 health + /docs + /openapi.json + 5 个业务端点）。

- [ ] **Step 3: 提交**

```bash
git add src/kg_system/main.py
git commit -m "feat(main): FastAPI app + lifespan + router wiring"
```

---

### Task 20: `__main__.py` —— `python -m kg_system` 启动

**Files:**
- Create: `src/kg_system/__main__.py`

- [ ] **Step 1: 写 `__main__.py`**

```python
from __future__ import annotations

import uvicorn

from kg_system.core.config import get_settings


def main() -> None:
    s = get_settings()
    uvicorn.run(
        "kg_system.main:app",
        host=s.APP_HOST,
        port=s.APP_PORT,
        reload=s.APP_DEBUG,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证导入**

```bash
python -c "import kg_system.__main__ as m; print(callable(m.main))"
```

预期：`True`

- [ ] **Step 3: 提交**

```bash
git add src/kg_system/__main__.py
git commit -m "feat: python -m kg_system entrypoint"
```

---

### Task 21: `docker-compose.yml`

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: 写 `docker-compose.yml`**

```yaml
services:
  neo4j:
    image: neo4j:5-community
    container_name: kg-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_max__size: 1G
    volumes:
      - neo4j_data:/data
    healthcheck:
      test:
        - CMD-SHELL
        - cypher-shell -u neo4j -p $$NEO4J_PASSWORD "RETURN 1" || exit 1
      interval: 10s
      timeout: 5s
      retries: 30

  redis:
    image: redis:7-alpine
    container_name: kg-redis
    ports:
      - "6379:6379"
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  postgres:
    image: postgres:16-alpine
    container_name: kg-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DATABASE}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: .
    container_name: kg-api
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      REDIS_HOST: redis
      POSTGRES_HOST: postgres
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    command: uvicorn kg_system.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./src:/app/src
      - ./prompts:/app/prompts

volumes:
  neo4j_data:
  redis_data:
  postgres_data:
```

- [ ] **Step 2: 提交**（不在此处 build/up；T22 后再做端到端验证）

```bash
git add docker-compose.yml
git commit -m "chore: docker-compose for neo4j/redis/postgres/api"
```

---

### Task 22: `prompts/{entity,relation}_extraction.txt`

**Files:**
- Create: `prompts/entity_extraction.txt`
- Create: `prompts/relation_extraction.txt`

变量插值用 Python `str.format`：`{text}`、`{entity_types}`、`{entities}`、`{relation_types}`。JSON 大括号要双花括号转义。

- [ ] **Step 1: 写 `entity_extraction.txt`**

```
你是知识图谱抽取专家。请从下面的文本中抽取核心实体。

允许的实体类型: {entity_types}

输出严格的 JSON,schema:
{{
  "entities": [
    {{"name": "实体名", "type": "实体类型", "props": {{"key": "value"}}}}
  ]
}}

要求:
- 实体名使用文本中的原始表述
- type 必须在允许类型范围内
- props 仅在文本明确提及时填入,否则留空对象
- 不输出 JSON 之外的任何内容,不使用 markdown 代码块包裹

文本:
{text}
```

- [ ] **Step 2: 写 `relation_extraction.txt`**

```
你是知识图谱关系抽取专家。给定实体列表与文本,抽取实体之间的关系。

允许的关系类型: {relation_types}

实体列表(JSON): {entities}

输出严格的 JSON,schema:
{{
  "relations": [
    {{"head": "头实体名", "tail": "尾实体名", "relation": "关系类型", "props": {{"time": "..."}}, "weight": 0.9}}
  ]
}}

要求:
- head/tail 必须出现在实体列表的 name 中
- relation 必须在允许关系类型范围内
- weight 是 0-1 的置信度,默认 1.0
- 不输出 JSON 之外的任何内容,不使用 markdown 代码块包裹

文本:
{text}
```

- [ ] **Step 3: 验证 prompt 模板可被读取**

```bash
python -c "from kg_system.builder.extractor import _read_prompt; t = _read_prompt('prompts/entity_extraction.txt', 'prompts/entity_extraction.txt'); print(len(t))"
```

预期：输出 prompt 字符数（>100）。

- [ ] **Step 4: 验证 docker build 可通**

```bash
docker build -t kg-api:dev .
```

预期：build 成功，`Successfully tagged kg-api:dev`。

- [ ] **Step 5: 提交**

```bash
git add prompts/
git commit -m "feat(prompts): entity & relation extraction templates"
```

---

### Task 23: `frontend/graphpanel.vue` + `frontend/README.md` + 顶层 `README.md`

**Files:**
- Create: `frontend/graphpanel.vue`
- Create: `frontend/README.md`
- Create: `README.md`

- [ ] **Step 1: 写 `frontend/graphpanel.vue`**

```vue
<!--
  GraphPanel — 知识图谱子图可视化（Vue 3 + D3 v7 单文件组件）

  集成方式：见 frontend/README.md
  依赖：d3@7（npm 或 CDN）
  API 约定：POST {apiBaseUrl}/api/v1/kg/query
            body: {entity_name, depth, relation_types?}
            返回 ApiResponse<{nodes:[{id,name,type,props}], links:[{source,target,relation,weight}]}>
-->
<template>
  <div class="kg-graph-panel">
    <header class="kg-toolbar">
      <input v-model="entityInput" placeholder="实体名称" @keyup.enter="loadGraph" />
      <input type="number" v-model.number="depthInput" min="1" max="3" />
      <button @click="loadGraph" :disabled="loading">{{ loading ? "加载中..." : "查询" }}</button>
      <select multiple v-model="relationFilter" class="kg-rel-filter">
        <option v-for="r in availableRelations" :key="r" :value="r">{{ r }}</option>
      </select>
    </header>
    <div class="kg-canvas-wrap" ref="wrap">
      <svg ref="svgEl" :width="width" :height="height">
        <g ref="rootG">
          <line
            v-for="(l, i) in renderedLinks"
            :key="'l' + i"
            :x1="l.source.x"
            :y1="l.source.y"
            :x2="l.target.x"
            :y2="l.target.y"
            :stroke-width="Math.max(1, l.weight * 2)"
            stroke="#999"
            stroke-opacity="0.6"
          />
          <g v-for="n in nodes" :key="n.id" :transform="`translate(${n.x},${n.y})`">
            <circle :r="nodeRadius(n)" :fill="colorOf(n.type)" stroke="#fff" stroke-width="1.5" />
            <text dy="4" text-anchor="middle" font-size="10" fill="#222">{{ n.name }}</text>
          </g>
        </g>
      </svg>
      <aside v-if="selected" class="kg-detail">
        <h4>{{ selected.name }}</h4>
        <p>类型: {{ selected.type }}</p>
        <pre>{{ JSON.stringify(selected.props, null, 2) }}</pre>
        <button @click="selected = null">关闭</button>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from "vue";
import * as d3 from "d3";

const props = defineProps({
  apiBaseUrl: { type: String, default: "http://localhost:8000" },
  entityName: { type: String, default: "" },
  depth: { type: Number, default: 2 },
  authToken: { type: String, default: "" },
});

const entityInput = ref(props.entityName);
const depthInput = ref(props.depth);
const width = ref(900);
const height = ref(600);
const loading = ref(false);
const nodes = ref([]);
const links = ref([]);
const selected = ref(null);
const relationFilter = ref([]);
const wrap = ref(null);
const svgEl = ref(null);
const rootG = ref(null);

const availableRelations = computed(() => {
  return Array.from(new Set(links.value.map((l) => l.relation)));
});

const renderedLinks = computed(() => {
  if (relationFilter.value.length === 0) return links.value;
  return links.value.filter((l) => relationFilter.value.includes(l.relation));
});

const nodeRadius = (n) => {
  const deg = links.value.filter((l) => l.source.id === n.id || l.target.id === n.id).length;
  return 6 + Math.min(deg, 10);
};

const palette = ["#4e79a7", "#f28e2c", "#e15759", "#76b7b2", "#59a14f", "#edc949", "#af7aa1"];
const typeIndex = new Map();
const colorOf = (type) => {
  if (!typeIndex.has(type)) typeIndex.set(type, typeIndex.size);
  return palette[typeIndex.get(type) % palette.length];
};

let simulation = null;

async function loadGraph() {
  if (!entityInput.value.trim()) return;
  loading.value = true;
  try {
    const headers = { "Content-Type": "application/json" };
    if (props.authToken) headers["Authorization"] = `Bearer ${props.authToken}`;
    const res = await fetch(`${props.apiBaseUrl}/api/v1/kg/query`, {
      method: "POST",
      headers,
      body: JSON.stringify({ entity_name: entityInput.value, depth: depthInput.value }),
    });
    const env = await res.json();
    if (env.code !== 200) throw new Error(env.msg);
    const data = env.data || { nodes: [], links: [] };
    nodes.value = data.nodes.map((n) => ({ ...n }));
    links.value = data.links.map((l) => ({ ...l }));
    await nextTick();
    runSimulation();
  } finally {
    loading.value = false;
  }
}

function runSimulation() {
  if (simulation) simulation.stop();
  simulation = d3
    .forceSimulation(nodes.value)
    .force(
      "link",
      d3.forceLink(links.value).id((d) => d.id).distance(80)
    )
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width.value / 2, height.value / 2));

  d3.select(svgEl.value).call(
    d3.zoom().on("zoom", (event) => {
      d3.select(rootG.value).attr("transform", event.transform);
    })
  );
  d3.select(svgEl.value)
    .selectAll("g > g")
    .call(
      d3
        .drag()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    )
    .on("click", (event, d) => {
      selected.value = d;
    });
}

onMounted(() => {
  if (wrap.value) {
    width.value = wrap.value.clientWidth || 900;
    height.value = wrap.value.clientHeight || 600;
  }
  if (props.entityName) loadGraph();
});

watch(() => props.entityName, (v) => {
  entityInput.value = v;
  if (v) loadGraph();
});
</script>

<style scoped>
.kg-graph-panel { font-family: system-ui, sans-serif; }
.kg-toolbar { display: flex; gap: 8px; padding: 8px; align-items: center; }
.kg-toolbar input, .kg-toolbar button, .kg-toolbar select { padding: 6px 8px; }
.kg-rel-filter { min-width: 140px; }
.kg-canvas-wrap { position: relative; width: 100%; height: 600px; border: 1px solid #eee; }
.kg-canvas-wrap svg { display: block; }
.kg-detail {
  position: absolute; top: 8px; right: 8px; width: 260px;
  background: #fff; border: 1px solid #ddd; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.kg-detail pre { font-size: 12px; max-height: 200px; overflow: auto; }
</style>
```

- [ ] **Step 2: 写 `frontend/README.md`**

```markdown
# graphpanel.vue 集成说明

单文件 Vue 3 组件，用 D3 v7 力导向图渲染知识图谱子图。

## 在已有 Vue 工程中使用

```bash
npm i d3
```

```vue
<script setup>
import GraphPanel from "./graphpanel.vue";
</script>
<template>
  <GraphPanel
    api-base-url="http://localhost:8000"
    entity-name="张三"
    :depth="2"
    auth-token="<JWT>"
  />
</template>
```

## 纯 HTML + CDN 方式

```html
<script type="importmap">
{ "imports": { "vue": "https://unpkg.com/vue@3/dist/vue.esm-browser.js",
                "d3": "https://unpkg.com/d3@7/dist/d3.min.js" } }
</script>
```

挂载方式同上。

## API 约定

- 路径：`POST {apiBaseUrl}/api/v1/kg/query`
- 请求体：`{ "entity_name": string, "depth": 1..3, "relation_types": string[] | null }`
- 响应：`{ "code": 200, "msg": "success", "data": { "nodes": [...], "links": [...] } }`
  - `nodes[i]`: `{ id, name, type, props }`
  - `links[i]`: `{ source, target, relation, weight }`
```

- [ ] **Step 3: 写顶层 `README.md`**

```markdown
# Knowledge Graph System (Skeleton)

基于 LLM 的知识图谱构建与分析系统骨架。详细架构与设计见 [`设计与技术实现方案.md`](./设计与技术实现方案.md)。

## 当前状态

骨架阶段：核心链路（文本→LLM抽取→Neo4j 入库→子图查询）端到端可跑；推理、调用分析、告警、外部接口为占位。

## 快速开始（Docker Compose）

```bash
cp .env.example .env
# 编辑 .env：填 OPENAI_API_KEY / ANTHROPIC_API_KEY、设置 NEO4J_PASSWORD / REDIS_PASSWORD / POSTGRES_PASSWORD
docker compose up -d
# 访问 http://localhost:8000/docs
```

## 本地开发（不用 Docker）

```bash
pip install -e ".[dev]"
# 自行启动本地 Neo4j 与 Redis，或用 docker compose up -d neo4j redis
uvicorn kg_system.main:app --reload
```

## 目录结构

| 路径 | 作用 |
|---|---|
| `src/kg_system/core/` | 配置、异常、模型、日志 |
| `src/kg_system/storage/` | Neo4j / Redis 客户端 + schema |
| `src/kg_system/llm/` | LLM 工厂、缓存、调用埋点 |
| `src/kg_system/builder/` | 文本→实体→关系→入库 pipeline |
| `src/kg_system/kg_query/` | 图谱查询服务 |
| `src/kg_system/reasoning/` | LangGraph 推理（占位） |
| `src/kg_system/analysis/` | 调用分析与告警（占位） |
| `src/kg_system/api/` | FastAPI 路由与中间件 |
| `prompts/` | LLM Prompt 模板 |
| `frontend/graphpanel.vue` | D3 子图可视化 |

## 实现状态

| 模块 | 状态 |
|---|---|
| `core/`、`storage/`、`llm/`、`builder/`、`kg_query/` | 可跑 |
| `api/v1/kg.py` (`/kg/build`, `/kg/query`) | 可跑 |
| `reasoning/`、`analysis/` | 占位（StateGraph 装配完整，节点/聚合 NotImplemented） |
| `api/v1/reason.py`、`analysis.py`、`external.py` | 注册路由，返回 501 |

## 下一步

详见 `docs/superpowers/specs/2026-05-28-kg-skeleton-design.md` §9（不在骨架范围）。每一项可独立立项。
```

- [ ] **Step 4: 端到端验证（最重要）**

```bash
# 1. 起服务
docker compose up -d
docker compose ps
# 预期：4 个服务都 healthy 或 running

# 2. 拉日志看 startup_done
docker compose logs api | grep startup_done

# 3. 健康检查
curl -s http://localhost:8000/health
# 预期：{"code":200,"msg":"success","data":{"status":"ok"}}

# 4. 看 OpenAPI
curl -s http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print(sorted(d['paths'].keys()))"
# 预期路径包含 /health, /api/v1/kg/build, /api/v1/kg/query, /api/v1/reason/ask,
#       /api/v1/llm/analyze, /api/v1/kg/external/{subgraph,context,cypher,embed}

# 5. 占位端点应返回 501
TOKEN=$(python -c "from jose import jwt; from kg_system.core.config import get_settings; s=get_settings(); print(jwt.encode({'sub':'test'}, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM))")
curl -s -X POST http://localhost:8000/api/v1/reason/ask \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"hi"}'
# 预期：{"code":501,"msg":"not implemented in skeleton",...}

# 6. 核心路径（需有效 OPENAI_API_KEY）
curl -s -X POST http://localhost:8000/api/v1/kg/build \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"张三在北京的字节跳动工作。"}'
# 预期：data.entities_upserted >= 2, data.relations_upserted >= 1

# 7. 查询子图
curl -s -X POST http://localhost:8000/api/v1/kg/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_name":"张三","depth":2}'
# 预期：data.nodes 包含张三，links 含 RELATED_TO 边
```

若步骤 6 因没有真实 LLM key 跳过，需手动跑 step 7 时先用 `cypher-shell` 灌入测试数据：

```bash
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "MERGE (a:Entity {name:'张三',type:'Person',id:'a1'}) \
   MERGE (b:Entity {name:'字节跳动',type:'Organization',id:'b1'}) \
   MERGE (a)-[r:RELATED_TO {relation_type:'WORKS_FOR',weight:1.0,id:'r1'}]->(b)"
```

- [ ] **Step 5: 提交**

```bash
git add frontend/ README.md
git commit -m "feat(frontend): graphpanel.vue + README + project README"
```

---

## 验收清单（spec §8）

骨架交付完成后,验证下列条件全部满足:

1. `pip install -e ".[dev]"` 成功,无依赖冲突。
2. `python -c "import kg_system.main"` 成功。
3. `docker compose up -d` 后 4 个服务 healthy/running。
4. `http://localhost:8000/docs` 看到全部 API。
5. `/api/v1/kg/build` 提供合法 LLM 配置后返回正确计数。
6. `/api/v1/kg/query` 返回 `{nodes,links}` JSON。
7. 占位端点返回 501 + ApiResponse 包装。
8. `frontend/graphpanel.vue` 通过 `apiBaseUrl` 拉子图并渲染（手动浏览器验证）。

## 不在骨架范围（spec §9 同步项）

- Postgres 业务表与 ORM
- 真实语义缓存(embedding+向量检索)
- LangGraph 推理节点真实 LLM 调用
- 调用分析的 metrics 聚合与 dashboard
- 告警通知发送(webhook/email/SMS)
- K8s manifests
- 单元/集成测试
- 鉴权用户表与 token 颁发
- 流式 LLM 输出
- 多模态、Schema 对齐、Agent 工具节点

每一项后续独立立项。













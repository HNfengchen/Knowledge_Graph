# 知识图谱系统骨架 — 设计稿

- **日期**：2026-05-28
- **范围**：基于《设计与技术实现方案.md》生成"全栈骨架"，关键链路可跑通，其他模块给接口骨架 + 1-2 示例。
- **目标**：`docker compose up` 后，能调通 `POST /api/v1/kg/build` 与 `POST /api/v1/kg/query` 两个端点；其余端点存在路由与 schema，返回 501。

## 1. 决策摘要

通过澄清问答确认的范围决策：

| 决策项 | 选择 |
|---|---|
| 交付范围 | 全栈骨架（所有模块都生成壳代码） |
| 骨架深度 | 关键路径可跑通 + 其他模块占位 |
| 前端 | 仅 `graphpanel.vue` 单文件示例 + README |
| 部署 | 仅 `docker-compose.yml` |
| Python 项目结构 | `pyproject.toml` + `src/` 布局 |
| 测试 | 骨架阶段不写 |
| 模块组织 | 按业务能力分包（与方案模块一一对应） |

## 2. 顶层目录布局

```
Knowledge_Graph/
├── .env.example                        # 已存在
├── .gitignore                          # 已存在
├── 设计与技术实现方案.md
├── README.md                           # 新建：架构 + 启动说明 + 状态表
├── pyproject.toml                      # 包元数据 + 依赖
├── Dockerfile                          # 后端镜像
├── .dockerignore
├── docker-compose.yml                  # neo4j + redis + postgres + api
├── docs/
│   └── superpowers/specs/
│       └── 2026-05-28-kg-skeleton-design.md
├── frontend/
│   ├── graphpanel.vue                  # D3 力导向图单文件
│   └── README.md                       # 集成说明
├── prompts/
│   ├── entity_extraction.txt
│   └── relation_extraction.txt
└── src/
    └── kg_system/
```

- 包名 `kg_system`。
- 启动方式：`uvicorn kg_system.main:app` 或 `python -m kg_system`。
- 安装：`pip install -e ".[dev]"`。

## 3. `src/kg_system/` 包结构

```
src/kg_system/
├── __init__.py
├── __main__.py                   # python -m kg_system → uvicorn
├── main.py                       # FastAPI app 装配 + 路由 + lifespan
│
├── core/
│   ├── config.py                 # pydantic-settings → .env
│   ├── exceptions.py             # KGException 体系
│   ├── logging.py                # structlog 配置
│   └── models.py                 # 全局 Pydantic schemas
│
├── api/
│   ├── deps.py                   # auth / driver / limiter 依赖
│   ├── middleware.py             # 统一响应包装 + 异常处理
│   └── v1/
│       ├── kg.py                 # /kg/build, /kg/query    ✅ 可跑
│       ├── reason.py             # /reason/ask              🟡 501
│       ├── analysis.py           # /llm/analyze             🟡 501
│       └── external.py           # /kg/external/*           🟡 501
│
├── builder/                      # ✅ 核心可跑
│   ├── chunker.py
│   ├── extractor.py              # Entity/Relation Extractor
│   ├── disambiguator.py          # 骨架：按 (name,type) 完全匹配
│   └── pipeline.py               # LCEL 装配
│
├── reasoning/                    # 🟡 占位（graph 装配完整，节点 NotImplementedError）
│   ├── state.py
│   ├── nodes.py
│   └── graph.py
│
├── llm/                          # ✅ 核心可跑
│   ├── factory.py                # provider 工厂
│   ├── cache.py                  # 直���占位
│   └── callbacks.py              # 埋点 → Redis Stream
│
├── analysis/                     # 🟡 占位
│   ├── collector.py
│   ├── metrics.py
│   └── alerts.py                 # AlertManager + ALERT_RULES
│
├── storage/                      # ✅ 核心可跑
│   ├── neo4j_client.py
│   ├── redis_client.py
│   └── schemas.py                # 启动建约束/索引
│
└── kg_query/                     # ✅ 核心可跑
    └── service.py                # KGQueryService
```

### 3.1 模块间依赖规则

```
api/  →  builder, reasoning, kg_query, analysis  →  llm, storage  →  core
```

- `core/` 不依赖任何业务模块。
- `llm/`、`storage/` 只依赖 `core/`。
- 业务模块依赖 `llm/`、`storage/`、`core/`。
- `api/` 是最外层，只组合业务模块。

### 3.2 实现状态表

| 模块 | 状态 | 备注 |
|---|---|---|
| `core/` 全部 | ✅ 可跑 | 配置、日志、异常、模型 |
| `storage/neo4j_client.py` | ✅ 可跑 | upsert_entities / upsert_relations / match_subgraph |
| `storage/redis_client.py` | ✅ 可跑 | async 连接池 |
| `storage/schemas.py` | ✅ 可跑 | 启动建索引（幂等） |
| `llm/factory.py` | ✅ 可跑 | openai / anthropic / local |
| `llm/callbacks.py` | ✅ 可跑 | 埋点写 Stream |
| `builder/extractor.py` | ✅ 可跑 | LLM + Pydantic 解析 |
| `builder/pipeline.py` | ✅ 可跑 | chunk → extract → write |
| `api/v1/kg.py` | ✅ 可跑 | build / query |
| `kg_query/service.py` | ✅ 可跑 | query_subgraph |
| `builder/disambiguator.py` | 🟡 占位 | (name,type) 完全匹配 |
| `llm/cache.py` | 🟡 占位 | 直通 |
| `reasoning/*` | 🟡 占位 | 节点 NotImplementedError |
| `analysis/*` | 🟡 占位 | 类骨架 |
| `api/v1/reason.py` | 🟡 占位 | 返回 501 |
| `api/v1/analysis.py` | 🟡 占位 | 返回 501 |
| `api/v1/external.py` | 🟡 占位 | 返回 501 |

## 4. 数据流：两条可跑通路径

### 4.1 路径 A — `POST /api/v1/kg/build`

```
HTTP { "text", "doc_id" }
  → api/v1/kg.py build_endpoint
  → builder/pipeline.py KGBuildPipeline.run(text, doc_id)
      ├─ builder/chunker.py     chunk_text  → List[str]
      ├─ builder/extractor.py   EntityExtractor.extract
      │    └─ llm/factory.py    get_chat_model
      │         └─ llm/callbacks.py on_llm_end → Redis Stream
      ├─ builder/extractor.py   RelationExtractor.extract
      ├─ builder/disambiguator  Disambiguator.resolve
      │    └─ storage/neo4j_client.find_entity_by_name
      └─ storage/neo4j_client   upsert_entities + upsert_relations
  → ApiResponse { code:200, data:{ entities_upserted, relations_upserted, doc_id } }
```

### 4.2 路径 B — `POST /api/v1/kg/query`

```
HTTP { "entity_name", "depth" }
  → api/v1/kg.py query_endpoint
  → kg_query/service.py KGQueryService.query_subgraph
  → storage/neo4j_client.match_subgraph
       Cypher: MATCH (e:Entity {name:$name})-[r*1..d]-(n) RETURN ...
  → 转换为 SubgraphResult { nodes:[...], links:[...] }
  → ApiResponse
```

### 4.3 启动 lifespan

```
startup:
  1. core/config.py  load Settings (.env)
  2. core/logging.py configure structured logger
  3. storage/neo4j_client.py create async driver + verify_connectivity
  4. storage/redis_client.py create async pool + ping
  5. storage/schemas.py      apply constraints + indexes (idempotent)
  6. llm/factory.py          validate provider config
  7. analysis/collector.py   start background task (占位：仅启动空 task)
  yield
shutdown:
  反向关闭驱动 / 取消后台任务
```

### 4.4 占位端点统一行为

- 路由已注册、Pydantic schema 已定义、依赖注入已配置。
- 方法体：`raise HTTPException(501, "not implemented in skeleton")`。
- 这样 OpenAPI 文档（`/docs`）能完整展示所有 API。

## 5. 关键合约

### 5.1 `core/models.py`

```python
class ExtractedEntity(BaseModel):
    name: str
    type: str
    props: dict[str, Any] = {}
    source_chunk_id: str | None = None

class ExtractedRelation(BaseModel):
    head: str
    tail: str
    relation: str
    props: dict[str, Any] = {}
    weight: float = 1.0

class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    props: dict[str, Any] = {}

class GraphLink(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0

class SubgraphResult(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]

T = TypeVar("T")
class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    msg: str = "success"
    data: T | None = None
```

### 5.2 API 请求/响应

```python
# api/v1/kg.py
class BuildRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=settings.TEXT_MAX_LENGTH)
    doc_id: str
    metadata: dict[str, Any] = {}

class BuildResponse(BaseModel):
    doc_id: str
    chunks: int
    entities_upserted: int
    relations_upserted: int

class QueryRequest(BaseModel):
    entity_name: str
    depth: int = Field(2, ge=1, le=3)
    relation_types: list[str] | None = None

# api/v1/reason.py
class AskRequest(BaseModel):
    question: str
    max_steps: int = 5

class AskResponse(BaseModel):
    answer: str
    reasoning_trace: list[str]
    evidence: SubgraphResult
```

### 5.3 模块接口签名

```python
# builder/pipeline.py
class KGBuildPipeline:
    def __init__(self, llm: BaseChatModel, neo4j: Neo4jClient): ...
    async def run(self, text: str, doc_id: str) -> BuildResponse: ...

# builder/extractor.py
class EntityExtractor:
    async def extract(self, chunk: str) -> list[ExtractedEntity]: ...
class RelationExtractor:
    async def extract(self, chunk: str, entities: list[ExtractedEntity]) -> list[ExtractedRelation]: ...

# builder/disambiguator.py
class Disambiguator:
    async def resolve(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """骨架实现：按 (name, type) 完全匹配查现有节点，带上既有 id。"""

# storage/neo4j_client.py
class Neo4jClient:
    async def upsert_entities(self, entities: list[ExtractedEntity]) -> dict[str, str]: ...
    async def upsert_relations(self, relations: list[ExtractedRelation], name_to_id: dict[str, str]) -> int: ...
    async def match_subgraph(self, entity_name: str, depth: int, relation_types: list[str] | None) -> SubgraphResult: ...
    async def find_entity_by_name(self, name: str, type: str | None = None) -> GraphNode | None: ...
    async def execute_cypher(self, cypher: str, params: dict) -> list[dict]: ...

# llm/factory.py
def get_chat_model(provider: str | None = None) -> BaseChatModel:
    """provider: openai | anthropic | local；None 用 settings.LLM_DEFAULT_PROVIDER"""

# llm/callbacks.py
class AnalysisCallbackHandler(BaseCallbackHandler):
    """埋点 on_llm_start / on_llm_end / on_llm_error 写 Redis Stream。"""

# kg_query/service.py
class KGQueryService:
    async def query_subgraph(self, entity_name: str, depth: int, relation_types: list[str] | None) -> SubgraphResult: ...
    async def get_entity_context(self, entity_name: str, max_neighbors: int) -> str: ...

# reasoning/graph.py
def build_reasoning_graph() -> CompiledGraph:
    """返回编译好的 StateGraph；节点函数 raise NotImplementedError。"""

# analysis/alerts.py
class AlertManager:
    ALERT_RULES: dict[str, dict]
    async def evaluate(self, metrics: dict) -> list[Alert]:
        raise NotImplementedError
```

### 5.4 Neo4j Schema

���动时执行（`storage/schemas.py`，全部 `IF NOT EXISTS`）：

```cypher
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
  FOR (e:Entity) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT entity_name_type_unique IF NOT EXISTS
  FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE;

CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
  FOR (e:Entity) ON EACH [e.name, e.description];

CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
  FOR (e:Entity) ON e.embedding
  OPTIONS { indexConfig: {
    `vector.dimensions`: $dim,
    `vector.similarity_function`: 'cosine'
  } };
```

节点统一标签 `Entity`、关系统一类型 `RELATED_TO`，靠 `type` / `relation_type` 属性区分（与方案 §3.1 一致）。

### 5.5 配置加载

`core/config.py` 用 `pydantic-settings`，分组：
`AppSettings` / `LLMSettings` / `Neo4jSettings` / `RedisSettings` / `PostgresSettings` / `SecuritySettings` / `CORSSettings` / `BuilderSettings` / `ReasoningSettings` / `AlertSettings` / `CostSettings` / `CacheSettings` / `LoggingSettings`。

聚合到 `Settings` 单例，`get_settings()` 走 `@lru_cache`。字段对应 `.env.example` 全部键。

## 6. 部署、依赖、错误处理

### 6.1 `docker-compose.yml`

```yaml
services:
  neo4j:
    image: neo4j:5-community
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD}
      NEO4J_PLUGINS: '["apoc"]'
    volumes: ["neo4j_data:/data"]
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p $$NEO4J_PASSWORD 'RETURN 1'"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes: ["redis_data:/data"]

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DATABASE}
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      REDIS_HOST: redis
      POSTGRES_HOST: postgres
    depends_on:
      neo4j: { condition: service_healthy }
      redis: { condition: service_started }
      postgres: { condition: service_started }
    command: uvicorn kg_system.main:app --host 0.0.0.0 --port 8000 --reload
    volumes: ["./src:/app/src"]

volumes:
  neo4j_data:
  redis_data:
  postgres_data:
```

- `.env` 是真实配置（gitignore），compose `env_file: .env`。
- compose 内 `environment:` 段覆盖 host 为服务名，本地直接 `uvicorn` 时仍用 `.env` 里的 `localhost`。
- Postgres 起着但骨架未调用，便于后续填充。

### 6.2 `pyproject.toml` 依赖

**runtime**：
```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.9
pydantic-settings>=2.6
python-dotenv>=1.0
langchain>=0.3
langchain-core>=0.3
langchain-openai>=0.2
langchain-anthropic>=0.2
langgraph>=0.2
neo4j>=5.25
redis[hiredis]>=5.2
httpx>=0.27
structlog>=24.4
python-jose[cryptography]>=3.3
```

**dev extras**：
```
pytest>=8
pytest-asyncio>=0.24
ruff>=0.7
mypy>=1.13
```

暂不引入：`sqlalchemy`/`asyncpg`（Postgres 未用）、`sentence-transformers`/`numpy`（向量计算未实现）、`vllm`/`ollama` 客户端（用 OpenAI 兼容 base_url）。

### 6.3 错误处理

```python
# core/exceptions.py
class KGException(Exception):
    code: int = 500
    msg: str = "internal error"
class ConfigError(KGException):     code = 500
class LLMError(KGException):        code = 502
class LLMTimeoutError(LLMError):    code = 504
class Neo4jError(KGException):      code = 503
class EntityNotFound(KGException):  code = 404
class InvalidInput(KGException):    code = 400
class AuthError(KGException):       code = 401
class RateLimitError(KGException):  code = 429
```

`api/middleware.py` 注册三个异常处理器：
1. `KGException` → `ApiResponse(code=e.code, msg=e.msg)`，HTTP 状态 = `e.code`。
2. `RequestValidationError` → `code=400`。
3. 兜底 `Exception` → `code=500`，日志记 traceback、响应不暴露详情。

成功响应也走统一包装：路由函数返回业务 model，中间件包成 `ApiResponse`。例外：`/docs`、`/openapi.json`、`/health` 直通。

### 6.4 认证

- 业务端点：`Bearer Token`（JWT，`api/deps.py::require_user`）。骨架仅校验 token 非空 + 签名，不查用户表。
- `/llm/analyze`：`Admin Token`（`api/deps.py::require_admin`，比对 `settings.ADMIN_TOKEN`）。
- `/kg/external/*`：`X-API-Key` + IP 白名单（`api/deps.py::require_external`）。

### 6.5 日志

`core/logging.py` 用 `structlog`，按 `LOG_FORMAT=json|console` 切换。
请求中间件给每请求注入 `request_id`，贯穿到 LLM callback 的 metadata，方便后续在调用分析里关联。

## 7. 前端、Prompt、README、Dockerfile

### 7.1 `frontend/graphpanel.vue`

单文件 Vue3 组件。挂在宿主工程里 `import GraphPanel from './graphpanel.vue'` 即用。**不带 npm 工程**。

**Props**：
- `apiBaseUrl: string`（默认 `http://localhost:8000`）
- `entityName: string`（初始查询实体）
- `depth: number`（默认 2）

**实现**：
- `<script setup>`：`onMounted` 调 `fetch(${apiBaseUrl}/api/v1/kg/query)` → 拿到 `{nodes, links}`。
- D3 力导向图：`d3.forceSimulation` + `forceLink/forceManyBody/forceCenter`。
- 视觉编码：`fill` 按 `type` 映射 5 色；`r` 按度数；边 `stroke-width` 按 `weight`。
- 交互：`d3.zoom()` 绑根 `<g>`；`d3.drag()` 绑节点；点节点弹 `<aside>` 显示 props。
- 关系类型筛选：顶部 `<select multiple>`，Vue 响应式过滤 `links`。

**外部依赖**：`d3` v7。

**`frontend/README.md`**：在已有 Vue 工程中集成（`npm i d3`）/ 纯 HTML CDN 跑 / API 响应格式约定。

### 7.2 Prompt 模板

`prompts/entity_extraction.txt` 与 `prompts/relation_extraction.txt`。变量插值用 Python `str.format`（双花括号转义 JSON 大括号）。

骨架内路径默认指向仓库内相对路径（`prompts/entity_extraction.txt`），不是 `.env.example` 里的 `/app/prompts`——`builder/extractor.py` 优先读 `settings.ENTITY_EXTRACTION_PROMPT_TEMPLATES`，若文件不存在 fallback 到包内相对路径。

### 7.3 顶层 `README.md`

章节：项目简介 → 架构图（复用方案 mermaid）→ 目录结构 → 快速开始（compose）→ 本地开发（不用 compose）→ 实现状态表 → 下一步。

### 7.4 `Dockerfile`

```
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY src ./src
COPY prompts ./prompts
EXPOSE 8000
CMD ["uvicorn", "kg_system.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`：`frontend/`、`docs/`、`.env`、`__pycache__`、`*.md`。

## 8. 验收标准

骨架交付后应满足：

1. `pip install -e ".[dev]"` 成功，无依赖冲突。
2. `python -c "import kg_system.main"` 成功，无 import 错误。
3. `docker compose up -d` 后，4 个服务（neo4j/redis/postgres/api）健康。
4. 访问 `http://localhost:8000/docs` 看到全部 API（含 501 占位端点）。
5. `POST /api/v1/kg/build` 提供合法 LLM 配置后，能成功调 LLM、写入 Neo4j、返回 entity/relation 计数。
6. `POST /api/v1/kg/query` 能从 Neo4j 返回 `{nodes, links}` JSON。
7. 占位端点返回 HTTP 501 + `ApiResponse(code=501, msg="not implemented in skeleton")`。
8. `frontend/graphpanel.vue` 在浏览器里加载后能通过 `apiBaseUrl` 拉到子图并渲染。

## 9. 不在骨架范围

明确**不做**：

- Postgres 业务表设计与 ORM 代码（Postgres 容器起着但代码不使用）。
- 真实的语义缓存（embedding + 向量检索）——`llm/cache.py` 直通。
- LangGraph 推理节点的真实 LLM 调用——`reasoning/nodes.py` 全部 `NotImplementedError`。
- 调用分析的 metrics 聚合与 dashboard——`analysis/*` 全部占位。
- 告警通知发送（webhook/email/SMS）——`AlertManager` 占位。
- K8s manifests（方案 §10.1 提到但本骨架不出）。
- 单元/集成测试。
- 鉴权的用户表与 token 颁发——只有 verify。
- 流式 LLM 输出。
- 多模态、Schema 对齐、Agent 工具节点（方案 §10.2 的扩展项）。

后续每一项可独立立项，按 spec → plan → 实现 的流程推进。

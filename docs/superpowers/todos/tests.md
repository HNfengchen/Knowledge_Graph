# tests —— 单元 / 集成 / e2e 测试

## 目标

骨架阶段刻意零测试。二期任何模块工作开始前，**先**铺好测试基础设施 + 关键路径用例，把 `/kg/build`、`/kg/query` 锁死，再放手扩功能。

## 当前状态

- 无 `tests/` 目录。
- `pyproject.toml` 无 dev deps。
- CI 未配置。

## 范围

- **入**：现有所有可执行模块（不含 `NotImplementedInSkeleton` 的占位）。
- **出**：`pytest -q` 全绿 + 覆盖率报告。
- **不在范围**：性能压测（独立 perf suite，远期）。

## 子任务

### 基础设施

- [ ] **T1：依赖 + 目录**
  - `pyproject.toml [project.optional-dependencies] dev`：`pytest>=8`、`pytest-asyncio>=0.23`、`pytest-cov>=5`、`httpx>=0.27`、`testcontainers>=4`（neo4j/redis/postgres）、`fakeredis>=2`、`respx`。
  - 顶层 `tests/{unit,integration,e2e}` 三层；`conftest.py` 顶层 + 各层。
  - `pytest.ini` (或 `[tool.pytest.ini_options]`)：`asyncio_mode = auto`、`testpaths = tests`、`addopts = -ra --strict-markers --cov=kg_system --cov-report=term-missing`。

- [ ] **T2：fixtures**
  - `settings_fixture`：`monkeypatch.setenv` 灌测试用 env。
  - `neo4j_fixture`（integration）：testcontainers `Neo4jContainer`，每个 module 一份；用完 wipe (`MATCH (n) DETACH DELETE n`)。
  - `redis_fixture`（unit 用 fakeredis；integration 用 testcontainers）。
  - `client_fixture`：`AsyncClient(transport=ASGITransport(app))`。
  - 验收：3 个 container fixture 启动 < 30s（首次镜像缓存后）。

- [ ] **T3：LLM 假驱动**
  - `tests/fakes/llm.py:FakeChatModel(BaseChatModel)`：按入参返回预置 JSON；可注入异常。
  - `monkeypatch` 替换 `llm.factory.get_chat_model`。
  - 验收：build pipeline 全程不联网。

### Unit

- [ ] **T4：core**
  - `models` Pydantic 边界（必填 / max_length）；`exceptions` HTTP 映射。
- [ ] **T5：splitter**
  - 英文 / 中文 / 混排 chunking 边界。
- [ ] **T6：extractor**
  - 解析 LLM 返回的边界 JSON（含多余 ``` / 多余字段 / 空数组）。
- [ ] **T7：disambiguator (现行 stub)**
  - `(name,type)` 匹配 vs 不匹配。
- [ ] **T8：kg_query.service**
  - `query_subgraph` 在 mock Neo4j 下深度边界、空结果。
- [ ] **T9：api/deps**
  - `require_user` 三种失败 + 一种成功；`require_admin` 比对；`require_external` IP 白名单。
- [ ] **T10：api/middleware**
  - 异常 handler 把 `KGError` 系列正确映射；request_id 透传。

### Integration

- [ ] **T11：build → query 闭环**
  - 真 Neo4j + fakes LLM，POST `/kg/build` 灌一段中文文本，再 POST `/kg/query` 返回 `nodes ≥ 2, edges ≥ 1`。
  - 验收：响应 envelope `success=true`。
- [ ] **T12：schema 自检**
  - 启动后 `SHOW INDEXES` 含 `entity_name_unique` / `entity_name_fulltext` / `entity_embedding`。
- [ ] **T13：health**
  - `/health` 含 neo4j/redis 状态。

### E2E

- [ ] **T14：docker-compose smoke**
  - `docker compose up -d`，等 healthy，curl `/health`、跑一次 build + query。
  - 验收：CI matrix 跑过。

### CI

- [ ] **T15：GitHub Actions**
  - `.github/workflows/test.yml`：3.11/3.12 矩阵 → `pip install -e ".[dev]"` → `pytest`。
  - covered 阈值：line ≥ 70%（骨架基线，逐期上调）。
- [ ] **T16：lint**
  - `ruff check .` + `ruff format --check .`；`mypy --strict src/kg_system`。

### 文档

- [ ] **T17：CONTRIBUTING.md**
  - 列出本机如何起 testcontainers、跳过 e2e 的 marker 用法（`pytest -m "not e2e"`）。

## 依赖

- 二期任意模块开工前必须先完成 T1–T3。
- 与所有 todo 文件双向：每个 todo 的「验收」条目是用例输入清单。

## 参考

- spec §9 非目标列表（第一项就是「无测试」）。
- 设计方案 §8（质量门禁）。

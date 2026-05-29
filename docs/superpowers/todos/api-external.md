# api/external —— `/api/v1/kg/external/*` 落地

## 目标

为外部系统（如其他 LLM Agent、业务后端）提供受控的图谱访问能力：子图取数、上下文摘要、只读 Cypher、文本 embedding。spec §4.5。

## 当前状态

`src/kg_system/api/v1/external.py`：4 个端点全部 `raise NotImplementedInSkeleton()`，受 `require_external` 守护（X-API-Key + IP 白名单已实现）。

## 范围

- **入**：四组 Schema 已定义（`SubgraphReq` / `ContextReq` / `CypherReq` / `EmbedReq`）。
- **出**：
  - `/subgraph` → `SubgraphResult`
  - `/context` → `{summary: str, neighbors: list[dict], evidence: SubgraphResult}`
  - `/cypher` → `list[dict]` 行
  - `/embed` → `list[list[float]]`
- **不在范围**：写入 / 改图（外部禁写）；订阅式推送（远期 webhook）。

## 子任务

### /subgraph

- [ ] **T1：复用 KGQueryService**
  - 直接调 `kg.query_subgraph(name, depth, relation_types)`。与 `/api/v1/kg/query` 同实现，但加：
    - `Cache-Control: max-age=60`；同名查询走 Redis Hash 缓存（key `ext:sg:{hash}` TTL 60s）。
  - 验收：连续两次请求第二次命中缓存（hit log）。

### /context

- [ ] **T2：摘要节点 + 邻居**
  - 取 1 跳邻居（最多 `max_neighbors`，按度数 / 时间倒序）。
  - 用 LLM 生成中文摘要：`prompt = "围绕 {entity}，结合下列邻居关系总结其角色 / 作用 / 关键关联。{neighbors_yaml}"`。
  - LLM 走 [llm-cache.md](./llm-cache.md)。
  - 验收：`evidence.nodes` ≥ 1；`summary` 引用 ≥ 1 个邻居名。

### /cypher

- [ ] **T3：只读白名单解析**
  - 词法层面禁止：`CREATE / MERGE / DELETE / DETACH / SET / REMOVE / DROP / CALL db.*write* / LOAD CSV`。
  - 用 `re.search(r"\b(create|merge|delete|...)\b", cypher, re.I)` 兜底；建议引入 `neo4j-cypher-parser` 做 AST 校验。
  - 强制 `LIMIT EXTERNAL_CYPHER_MAX_ROWS`（默认 1000），未声明则自动尾追。
  - 验收：写类语句一律 400 + code=2003。

- [ ] **T4：超时**
  - `tx.timeout = EXTERNAL_CYPHER_TIMEOUT`（默认 5s）；超时映射 `RequestTimeout` 504。

- [ ] **T5：参数化执行**
  - 必须用 `params` 传值，禁止字符串拼接。Schema 已定义 `params: dict`。
  - 验收：参数名出现在 cypher 中且未被作为字面量替换。

### /embed

- [ ] **T6：批量 embedding**
  - 走 `llm/factory.py:get_embedding_model()`（与 [builder-disambiguator.md](./builder-disambiguator.md) 共享）。
  - 输入限制：`len(texts) ≤ EXTERNAL_EMBED_BATCH_MAX` (64)，单条 ≤ 8k tokens。
  - 验收：64 条文本一次返回 64 个向量，维度等于 `EMBEDDING_DIM`。

### 通用

- [ ] **T7：限流**
  - 按 `X-API-Key` Redis 计数：`kg:rl:{api_key}:{minute}`，阈值 `EXTERNAL_RATE_LIMIT_PER_MIN`（默认 60）。
  - 超限返回 429 + `Retry-After`。
  - 验收：1 分钟内第 61 个请求被拒。

- [ ] **T8：审计日志**
  - 写一条 `external_call` 事件：api_key 哈希、endpoint、payload size、响应码、耗时。
  - 验收：从 Stream 可还原一段时间内的所有外部访问。

- [ ] **T9：契约测试**
  - 与 [tests.md](./tests.md) 协作：`/cypher` 写类语句拒绝、`/embed` 维度断言、`/subgraph` 缓存命中。

## 依赖

- 鉴权 `require_external` 已实现（API Key + IP 白名单）。
- `KGQueryService` 已就绪。
- `/embed` 依赖 [builder-disambiguator.md](./builder-disambiguator.md) 同一份 `get_embedding_model()`。
- `/context` 依赖 [llm-cache.md](./llm-cache.md)。

## 参考

- spec §4.5、§5.3 `api/v1/external.py`。
- 设计方案 §4.5、§7（外部接入）。

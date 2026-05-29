# llm/cache —— 语义缓存

## 目标

复用近似 prompt 的历史响应，降低 LLM 调用成本与延迟。spec §4.2 + 设计方案 §4.2 设定：在 Redis 中存 query embedding + response，新请求相似度 ≥ `SEMANTIC_CACHE_SIMILARITY_THRESHOLD`（默认 0.95）直接返回。

## 当前状态

`src/kg_system/llm/cache.py`：`SemanticCache.get` 永远返回 None，`set` 是 no-op。`SEMANTIC_CACHE_ENABLED` 配置已在 `Settings`，未消费。

## 范围

- **入**：`(model_name, messages_or_prompt, params)`，输出：`AIMessage` / 流式片段。
- **出**：缓存命中返回 cached response；未命中请求上游并写缓存。
- **不在范围**：流式响应缓存（首期支持非流式）；多模态 prompt 缓存。

## 子任务

- [ ] **T1：缓存键 schema**
  - key：`{REDIS_KEY_PREFIX}sc:{provider}:{model}:{sha256(prompt+params)}`。
  - 同时维护向量索引：在 Redis 用 RediSearch / 简易 FAISS-on-disk；否则退化到 KV+本地内存 ANN。
  - 验收：键命名稳定，参数（temperature/max_tokens/seed）变更不命中。

- [ ] **T2：embedding 写入**
  - 入站 prompt 在调用 LLM **前** 计算 embedding，请求向量近邻 Top-1。
  - 命中阈值：`>= SEMANTIC_CACHE_SIMILARITY_THRESHOLD`。
  - 命中时直接返回；同时埋点 `cache_hit=true`。

- [ ] **T3：写入策略**
  - 仅在 LLM 成功返回后写；结构 `{prompt, embedding, response, model, ts, ttl}`。
  - TTL = `SEMANTIC_CACHE_TTL`（默认 86400s）。
  - 容量上限 `SEMANTIC_CACHE_MAX_SIZE`，LRU 淘汰。

- [ ] **T4：BaseChatModel 适配**
  - 提供包装器：`with_semantic_cache(model)` 返回新 BaseChatModel；其内部 `ainvoke` 先查缓存。
  - 兼容 `with_config({"callbacks": [...]})` 链。

- [ ] **T5：可观测性**
  - hit / miss / write 计数推到 `analysis/collector` 同一 Stream（事件 `cache_event`）。
  - 验收：调 100 个相似 prompt，hit_rate >= 90%。

- [ ] **T6：开关与回退**
  - `SEMANTIC_CACHE_ENABLED=false` 时整体短路；Redis 不可用时记 warning，不阻塞主调用。

## 依赖

- 需 embedding 模型（与 [builder-disambiguator.md](./builder-disambiguator.md) 共用一个工厂方法）。
- 需 Redis 5+ 模块化（如要 RediSearch 必须 Redis Stack；否则使用纯 KV + 本地 ANN）。
- 与 [analysis.md](./analysis.md) 共享埋点流。

## 参考

- spec §4.2、§5.3 `llm/cache.py`。
- 设计方案 §4.2。

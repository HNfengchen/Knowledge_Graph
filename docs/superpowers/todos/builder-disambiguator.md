# builder/disambiguator —— 实体消歧

## 目标

将 LLM 抽出的 `ExtractedEntity` 准确映射到图谱已有节点，避免重复实体与拼写歧义，为下游关系入库提供稳定 id。

## 当前状态

`src/kg_system/builder/disambiguator.py`：仅按 `(name, type)` 完全匹配查 Neo4j；命中则带回既有 props，否则原样返回（后续 `upsert_entities` MERGE）。

## 范围

- **入**：`list[ExtractedEntity]`（来自 `EntityExtractor`，单 chunk 内已去重）。
- **出**：`list[ExtractedEntity]`，已绑定既有 id（如有）/ 已合并别名指向同一规范名。
- **不在范围**：跨语言对齐、跨图谱 schema 融合（见 `multimodal-agents.md`）。

## 子任务

- [ ] **T1：embedding 计算与缓存**
  - 给 `ExtractedEntity` 计算向量（默认 `text-embedding-3-small`，dim 1536，按 `EMBEDDING_*` 配置）。
  - 批量请求；同一会话内 `(name,type)` 命中缓存跳过。
  - 验收：1k 实体抽取 + embedding 总时延 < 30s（OpenAI），失败有 retry。

- [ ] **T2：向量召回候选**
  - Cypher：调用 `entity_embedding` 向量索引 `db.index.vector.queryNodes`，Top-K=10，相似度 ≥ `ENTITY_SIMILARITY_THRESHOLD` (0.85)。
  - 验收：单实体召回 < 50ms（10 万节点级）。

- [ ] **T3：全文召回候选**
  - 利用 `entity_name_fulltext` 索引模糊匹配，过滤 `type` 一致项。
  - 与 T2 候选求并集后去重。

- [ ] **T4：rerank + 决策**
  - 候选评分：向量相似度 + 全文得分 + name Levenshtein + type 一致 (布尔)。
  - 阈值策略：≥ θ_high → 直接绑 id；θ_low ≤ s < θ_high → 走 LLM 二次判定（结构化 yes/no/uncertain）；< θ_low → 视为新实体。
  - 验收：内置 50 例黄金集 acc ≥ 0.9。

- [ ] **T5：合并 props**
  - 同一实体多 chunk 抽到的 props 求并；冲突 key 取 weight 高者并记录到 `provenance`。
  - 验收：单元测试覆盖 3 种合并冲突。

- [ ] **T6：失败兜底**
  - 向量索引未建 / 不可用时退化到现行 `(name,type)` 完全匹配，记 warning 日志。

## 依赖

- `storage/neo4j_client.py` 需新增 `vector_search_entities(embedding, top_k, threshold)` 与 `fulltext_search_entities(name, top_k)` 方法。
- `llm/factory.py` 需新增 `get_embedding_model()`（OpenAI / Ollama 兼容）。
- 与 [llm-cache.md](./llm-cache.md) 共享 embedding 客户端。

## 参考

- spec §3 节点属性 `embedding`；§5.4 Schema 中 `entity_embedding` 向量索引。
- 设计方案 §2.3、§3.2。

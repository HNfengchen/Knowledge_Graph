# 全模块实施计划

## 阶段 0：测试基础设施
- T0-1: `pyproject.toml` dev 依赖（pytest, pytest-asyncio, pytest-cov, httpx, fakeredis, respx）
- T0-2: `tests/{unit,integration,e2e}/` 目录 + 顶层 conftest.py
- T0-3: `FakeChatModel`（tests/fakes/llm.py）
- T0-4: `test_core` 单元测试（models, exceptions）
- T0-5: `test_api_deps` 单元测试（require_user, require_admin, require_external）
- T0-6: `test_api_middleware` + `test_builder_pipeline` 单元测试
- T0-7: 集成测试 `test_build_query_cycle`（fakes LLM + 真 Neo4j）

## 阶段 1a：实体消歧（builder-disambiguator）
- T1a-1: `llm/factory.py` 新增 `get_embedding_model()`
- T1a-2: `storage/neo4j_client.py` 新增 `vector_search_entities` / `fulltext_search_entities`
- T1a-3: `builder/disambiguator.py` 全链路实现（embedding → 向量召回 → 全文召回 → rerank → 合并）
- T1a-4: 单元测试覆盖消歧各分支

## 阶段 1b：推理（reasoning + api-reason）
- T1b-1: `reasoning/nodes.py` 实现 retrieve_node（NER + 子图检索）
- T1b-2: `reasoning/nodes.py` 实现 reason_node（LLM 多步推理）
- T1b-3: `reasoning/nodes.py` 实现 decide_node + generate_node
- T1b-4: `api/v1/reason.py` 实现 `/reason/ask` 端点
- T1b-5: Cypher 生成兜底 + 超时 / 限流

## 阶段 2：LLM 缓存、分析、外部 API、鉴权
- T2-1: `llm/cache.py` 语义缓存完整实现
- T2-2: `analysis/collector.py` 真正消费 Redis Stream
- T2-3: `analysis/metrics.py` 聚合实现（QPS/延迟/成本）
- T2-4: `analysis/alerts.py` 评估 + 通知 + 调度器
- T2-5: `api/v1/analysis.py` /analyze 端点
- T2-6: `api/v1/external.py` 4 个外部端点
- T2-7: auth 模块（JWT + /auth 路由 + require_user 升级）

## 阶段 3：测试完善 + 集成验证
- T3-1: 集成测试覆盖所有新端点
- T3-2: lint + typecheck
- T3-3: 修复所有问题

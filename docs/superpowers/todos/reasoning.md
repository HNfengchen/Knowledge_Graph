# reasoning —— LangGraph 推理实现

## 目标

把骨架阶段的 4 节点 `StateGraph` 装配（state / nodes 桩 / graph）落到真实推理：基于用户问题，从 Neo4j 检索子图、LLM 多步推导、必要时迭代查询，最终返回答案 + 推理 trace + 证据子图。对应 `/api/v1/reason/ask`。

## 当前状态

- `src/kg_system/reasoning/state.py`：`ReasonerState` TypedDict 完整。
- `src/kg_system/reasoning/nodes.py`：`retrieve_node` / `reason_node` / `decide_node` / `generate_node` 全部 `raise NotImplementedInSkeleton`；`route_after_decide` 已可读 `state["next_action"]`。
- `src/kg_system/reasoning/graph.py`：`build_reasoning_graph()` 装好 4 节点 + 条件边，能 compile，但 invoke 立即抛错。

## 范围

- **入**：`question: str`，`max_steps: int`。
- **出**：`answer`、`reasoning_trace: list[str]`、`evidence: SubgraphResult`。
- **不在范围**：Agent 工具节点 / 联网搜索（见 `multimodal-agents.md`）。

## 子任务

- [ ] **T1：question → 实体识别**
  - 在 `retrieve_node` 之前增加 NER：复用 `EntityExtractor` 仅抽 entity（不抽 relation）。
  - 验收：100 例问句 entity F1 ≥ 0.85。

- [ ] **T2：retrieve_node**
  - 对每个 NER 实体调 `KGQueryService.query_subgraph(name, depth=REASONING_SUBGRAPH_DEPTH, max_nodes=REASONING_SUBGRAPH_MAX_NODES)`。
  - 多实体子图并集 → `state["subgraph"]` (`SubgraphResult` JSON 序列化)。
  - 验收：超量节点按度数截断到 `MAX_NODES`。

- [ ] **T3：reason_node**
  - 走 LLM (`temperature=REASONING_TEMPERATURE`)：把子图 + 问题塞进 prompt，要求结构化输出 `{thought, next_action: reason|retrieve|generate, query?: str}`。
  - `state["reasoning_trace"]` 追加 thought；更新 `next_action`。
  - 验收：单元测试覆盖 3 类决策分支。

- [ ] **T4：retrieve 二次查询**
  - 当 `next_action=retrieve` 时，把 `state["query"]` 作为新实体名重入 `retrieve_node`，子图并入既有。
  - 防环：`step_count` 累加，超 `REASONING_MAX_STEPS` 强制走 generate。

- [ ] **T5：generate_node**
  - 基于完整 trace + subgraph 生成最终答案；要求引用子图节点 id。
  - 验收：答案中至少包含 1 个子图节点引用。

- [ ] **T6：Cypher 生成兜底**
  - 当 NER 返回空时，走 LLM 生成 Cypher，经白名单 (只读) 校验后执行；失败回退到全文检索。
  - 验收：禁止任何 WRITE / DELETE / DROP 关键词。

- [ ] **T7：tracing & 可观测**
  - 整个流程接 `AnalysisCallbackHandler`，每步耗时与 token 写 Stream。
  - 验收：从 Stream 可还原一次 ask 的全部 LLM 调用。

- [ ] **T8：缓存**
  - 同 question 缓存命中走 [llm-cache.md](./llm-cache.md)。

## 依赖

- [api-reason.md](./api-reason.md) 同步落地。
- 需要 `EntityExtractor`（已有）+ `KGQueryService`（已有）。
- 与 [llm-cache.md](./llm-cache.md) 串。

## 参考

- spec §5.3 `reasoning/graph.py`、§4.x 的 `/reason/ask` 期望响应。
- 设计方案 §5。

# api/reason —— `/api/v1/reason/*` 落地

## 目标

将 [reasoning.md](./reasoning.md) 实现的 LangGraph 推理图通过 HTTP 暴露：`POST /api/v1/reason/ask` 返回 `{answer, reasoning_trace, evidence}`。spec §4.3。

## 当前状态

`src/kg_system/api/v1/reason.py`：
- `AskRequest{question, max_steps}` / `AskResponse{answer, reasoning_trace, evidence}` Schema 已定义。
- `ask_endpoint` 仅 `raise NotImplementedInSkeleton()`。
- 已挂在 main 的 `/api/v1` 路由组，受 `require_user` 守护。

## 范围

- **入**：JSON `{question: str, max_steps: int (1..20, default 5)}`。
- **出**：`ApiResponse[AskResponse]`，`evidence` 为 `SubgraphResult`。
- **不在范围**：流式 SSE（见 [streaming-llm.md](./streaming-llm.md)）；多轮会话上下文。

## 子任务

- [ ] **T1：依赖注入**
  - 新增 `get_reasoning_graph()` deps（缓存 compiled graph 单例，避免每请求重建）。
  - LLM 走 `get_chat_model()` + `AnalysisCallbackHandler` 包装。
  - 验收：连续 3 次请求复用同一 graph 实例。

- [ ] **T2：endpoint 主体**
  - 调 `graph.ainvoke(initial_state, config={"configurable": {...}, "callbacks": [...]})`。
  - `initial_state = {"question": body.question, "max_steps": body.max_steps, "step_count": 0, "reasoning_trace": [], "subgraph": None}`。
  - 出参映射：`AskResponse(answer=state["answer"], reasoning_trace=state["reasoning_trace"], evidence=state["subgraph"])`。
  - 验收：金句 fixture「Alan Turing 提出过哪些重要概念？」走通且返回非空 evidence。

- [ ] **T3：超时与限流**
  - `asyncio.wait_for(..., timeout=REASONING_TIMEOUT)`，默认 60s。
  - 入参 `question` 长度 ≤ `QUESTION_MAX_LENGTH`，超限抛 `InvalidInput`。
  - 验收：人为设 `max_steps=20` + 卡死 LLM 模拟，60s 后返回 `RequestTimeout`。

- [ ] **T4：错误映射**
  - 子图为空 → `EmptySubgraph` (新增 exception)，HTTP 200 但 `data.evidence.nodes=[]`，answer 走 LLM 生成「未在图谱中找到」回退。
  - LLM 调用失败 → `LLMUpstreamError`，由全局 handler 映射为 502。
  - 验收：mock LLM 抛错，响应 502 且 envelope `code=2002`（按 `core/exceptions.py` 编码）。

- [ ] **T5：可观测**
  - request_id 透传到 graph 的 `RunnableConfig.metadata`。
  - 整次推理写一条 `reason_request` 事件到 Stream，含 step_count、cache_hit、tokens、duration。
  - 验收：从 Stream 能 join 出对应 `request_id`。

- [ ] **T6：契约测试**
  - 与 [tests.md](./tests.md) 协作：使用 fakes 跑 `/reason/ask`，断言响应字段齐全、`evidence` 节点 ≤ `REASONING_SUBGRAPH_MAX_NODES`。

## 依赖

- [reasoning.md](./reasoning.md) T1–T5 必须先就绪。
- 与 [analysis.md](./analysis.md) 共享 callback 流。
- 入参鉴权沿用 `require_user`。

## 参考

- spec §4.3、§5.3 `api/v1/reason.py`。
- 设计方案 §5。

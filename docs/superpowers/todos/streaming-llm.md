# streaming-llm —— LLM 流式输出 (SSE)

## 目标

把 `/reason/ask` 与未来的 chat 接口改造为 Server-Sent Events，让前端 `graphpanel.vue` 能实时渲染 token 与 reasoning trace。

## 当前状态

- `llm/factory.py:get_chat_model` 返回 `BaseChatModel`，调用方用 `ainvoke` 同步。
- `api/v1/reason.py` 返回完整 `AskResponse` JSON，无 streaming。
- `frontend/graphpanel.vue` 仅支持完成态结果显示。

## 范围

- **入**：`/reason/ask` 入参与现状一致；前端可附 `Accept: text/event-stream` 或路由 `/reason/ask/stream`。
- **出**：SSE 事件流：`data: {"type":"token","content":"..."}\n\n` 等。
- **不在范围**：WebSocket（成本高于收益，先 SSE）；LLM 调用以外的流（图谱构建进度可后续做）。

## 子任务

### 协议

- [ ] **T1：事件类型**
  - 协议：
    ```
    event: token        data: {"delta":"片段"}
    event: trace        data: {"step":1,"thought":"..."}
    event: subgraph     data: <SubgraphResult JSON>
    event: done         data: {"answer":"...","duration_ms":...}
    event: error        data: {"code":...,"message":"..."}
    ```
  - 心跳：每 15s `: keepalive\n\n`，防中间网关超时关连接。
  - 验收：`curl -N` 能拿到上述事件序列。

### 后端

- [ ] **T2：endpoint**
  - 新增 `POST /api/v1/reason/ask/stream`，返回 `StreamingResponse(media_type="text/event-stream")`。
  - 沿用 `AskRequest` schema + `require_user`。
  - 验收：完整事件序列以 `event: done` 结束。

- [ ] **T3：LangGraph stream 适配**
  - 用 `graph.astream_events(initial_state, version="v2")` 拿底层 token。
  - 过滤事件 → 转换为本协议；同时把 reasoning_trace 的每次追加映射到 `event: trace`。
  - 验收：单步 reason_node 会先 trace 再 token。

- [ ] **T4：取消传播**
  - 客户端断开时 `request.is_disconnected()` 检测，取消上游 LLM async task。
  - 验收：客户端关连接后 1s 内 LLM 调用被 cancel（日志可见）。

- [ ] **T5：错误传播**
  - 异常先吐 `event: error` 再关流，HTTP 状态保持 200（SSE 规范要求）。
  - 验收：mock LLM 抛错，前端能拿到错误事件。

- [ ] **T6：缓存与 stream 共存**
  - 命中 [llm-cache.md](./llm-cache.md) 时一次性 `event: token` 全量字符串后立即 `done`，不强行假装流。
  - 验收：cache hit 测试用例 < 50ms 完成。

### 前端

- [ ] **T7：graphpanel.vue 接入**
  - 用 `EventSource` 或 `fetch` + `ReadableStream`（POST 必须 fetch）。
  - 增量拼接 answer，绘制 trace 步骤；`subgraph` 事件触发图谱重渲染。
  - 验收：用户输入问题后 < 1s 看到首 token。

- [ ] **T8：UI 状态机**
  - states: idle → connecting → streaming → done | error。
  - "停止生成" 按钮发 `AbortController.abort()`。
  - 验收：abort 后服务端日志看到 cancel。

### 鉴权

- [ ] **T9：token 透传**
  - SSE 仍用 `Authorization: Bearer`，与普通端点一致。
  - 验收：缺 token → 立即 401，不开流。

- [ ] **T10：限流**
  - 同一用户并发 stream ≤ `STREAM_CONCURRENT_PER_USER`（默认 2）；超限 429。
  - 验收：第 3 路 stream 被拒。

## 依赖

- [reasoning.md](./reasoning.md) 必须先就绪（stream 是它的视图）。
- [auth.md](./auth.md) T2 JWT 已落地（access token 短 TTL 适合 SSE）。

## 参考

- spec §4.3 备注「未来流式」；设计方案 §5。
- LangChain `astream_events` v2 文档。

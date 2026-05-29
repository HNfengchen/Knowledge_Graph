# multimodal-agents —— 多模态 / Schema 对齐 / Agent 工具节点

## 目标

把图谱构建 / 推理从「纯文本 + 单图谱 + 顺序流程」扩展到：图像 / 表格 / PDF 等多模态输入；多源 schema 对齐；LangGraph 内 agent 工具节点（联网、调外部 API、跨图谱查询）。spec §9 远期项。

## 当前状态

- `KGBuildPipeline` 仅吃 `text`。
- `reasoning/graph.py` 4 节点直线推理，无 tool calling。
- `core/models` 无多模态 chunk 概念。
- 无 schema 注册中心 / 跨图谱映射代码。

## 范围

- **入**：图像 / 表格 / 结构化 JSON / 外部图谱端点。
- **出**：可消费的 `entity / relation`，以及 reasoning 时按需调用工具的能力。
- **不在范围**：训练定制视觉模型；自建向量数据库（继续用 Neo4j 向量索引）。

## 子任务

### 多模态构建

- [ ] **T1：Chunk 抽象**
  - 新增 `core/models.MediaChunk{kind: text|image|table|pdf_page, payload: bytes|str, ocr_text?, caption?}`。
  - `splitter.py` 拆分时识别非文本 part（PDF 走 `pypdfium2`，图片走 BLIP-2 caption）。
  - 验收：含图 PDF 拆分后既有文字 chunk 也有图片 chunk。

- [ ] **T2：视觉 LLM 抽取**
  - `llm/factory.py:get_vision_model()`（GPT-4o / Claude 3.5 / Qwen-VL）。
  - 复用 `EntityExtractor` 接口，prompt 模版扩展支持 base64 图。
  - 验收：一张关系图截图可抽出 ≥ 3 个实体。

- [ ] **T3：表格解析**
  - 表格 → DataFrame → 行实体 + 列关系；按表头自动选 primary key。
  - 验收：5 行 3 列表格 → 5 实体 + 行属性。

### Schema 对齐

- [ ] **T4：Schema 注册**
  - 新增 `core/schema.py:SchemaRegistry`：实体类型 / 关系类型白名单 + 别名。
  - 抽取产物先 normalize：`Person -> 人物`、`is_friend_of -> 朋友`。
  - 验收：跨语料抽取的同义类型合并为同一 label。

- [ ] **T5：跨图谱映射**
  - 引入 `kg_query/external_graph.py`：对接 Wikidata / DBpedia 公开 SPARQL 端点；查询接口与 `KGQueryService` 对齐。
  - 联合查询：本地 → Wikidata fallback。
  - 验收：「Alan Turing」本地缺失时从 Wikidata 取回基本属性写入。

- [ ] **T6：实体对齐**
  - 在 disambiguator 之上加跨图谱对齐：本地实体 ↔ Wikidata QID。
  - 表 schema：在 `Entity` 节点加 `external_ids: {wikidata: "Q7251", ...}`。
  - 验收：相同 QID 的实体走 MERGE。

### Agent 工具节点

- [ ] **T7：tool 节点装配**
  - 在 `reasoning/graph.py` 增 `tools_node`：路由触发条件 `next_action="tool"` + `tool_name`。
  - 内置工具：`web_search` (Tavily/Bing)、`wikipedia`、`calculator`、`code_exec` (受限 sandbox)。
  - 验收：「巴黎到伦敦多远」需 web_search 能给出 trace 片段。

- [ ] **T8：tool 鉴权与配额**
  - 每个工具走独立 API Key（settings 注入）；调用计数 + 单用户日额度。
  - 验收：超额返回 trace 提示「工具不可用」并降级到 LLM 推理。

- [ ] **T9：工具失败回退**
  - 工具异常 → trace 记录 → 重新走 reason_node 决定是否换工具或直接 generate。
  - 验收：网络超时 fixture 下 graph 不死循环。

### Schema-aware reasoning

- [ ] **T10：基于 schema 的查询规划**
  - reason_node 用 schema metadata 帮助生成 Cypher（避免错 label）。
  - 验收：对未声明的 label 拒绝查询。

### 安全

- [ ] **T11：code_exec sandbox**
  - 走 [restricted-python](https://restrictedpython.readthedocs.io) 或子进程 + seccomp。
  - 禁用 IO / 网络；CPU 1s / 内存 128MB 限制。
  - 验收：`os.system` 被拒。

- [ ] **T12：多模态 PII 风险**
  - 图像 OCR 后过滤身份证 / 银行卡 regex；命中 mask 后再入图。
  - 验收：测试 fixture 含模拟身份证号被替换为 `[REDACTED]`。

## 依赖

- 严重依赖 [reasoning.md](./reasoning.md) 已落地。
- 依赖 [llm-cache.md](./llm-cache.md) 复用 embedding。
- 依赖 [api-external.md](./api-external.md) 的限流 / 审计同套机制。

## 参考

- spec §9 远期非目标列表（多模态 / agent / schema）。
- 设计方案 §11（扩展场景）。

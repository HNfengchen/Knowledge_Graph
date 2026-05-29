# 未完成模块 TODO 总览

骨架阶段 (`docs/superpowers/specs/2026-05-28-kg-skeleton-design.md`) 已完成全部 23 任务。本目录列出 spec §9 / design §3.2 中标记为 🟡 占位 或 "不在骨架范围" 的所有模块的待完成清单，每条建议作为独立 spec → plan → 实现 立项推进。

## 文件索引

| # | 文件 | 主题 | 当前代码状态 | 优先级建议 |
|---|---|---|---|---|
| 1 | [builder-disambiguator.md](./builder-disambiguator.md) | 实体消歧（向量 + 全文） | 🟡 仅 (name,type) 完全匹配 | P1 — 影响图谱质量 |
| 2 | [llm-cache.md](./llm-cache.md) | 语义缓存（Embedding+向量检索） | 🟡 直通 stub | P2 — 性能/成本相关 |
| 3 | [reasoning.md](./reasoning.md) | LangGraph 推理节点真实实现 | 🟡 节点 NotImplemented | P1 — `/reason/ask` 阻塞中 |
| 4 | [analysis.md](./analysis.md) | 调用分析采集/聚合/告警 | 🟡 collector 空跑、metrics/alerts NotImplemented | P2 — 观测中心 |
| 5 | [api-reason.md](./api-reason.md) | `/api/v1/reason/*` | 🟡 501 占位 | 跟随 reasoning 落地 |
| 6 | [api-analysis.md](./api-analysis.md) | `/api/v1/llm/analyze` | 🟡 501 占位 | 跟随 analysis 落地 |
| 7 | [api-external.md](./api-external.md) | `/api/v1/kg/external/*` | 🟡 501 占位（4 个端点） | P2 — 对外集成 |
| 8 | [storage-postgres.md](./storage-postgres.md) | Postgres 业务表 + ORM | 🔴 容器起、未使用 | P3 — 业务侧需求驱动 |
| 9 | [auth.md](./auth.md) | 用户表 + token 颁发 | 🟡 仅 verify | P2 — 上线前必做 |
| 10 | [tests.md](./tests.md) | 单元 / 集成 / e2e 测试 | 🔴 无 | P0 — 任何二期前先补 |
| 11 | [k8s.md](./k8s.md) | K8s manifests / HPA / StatefulSet | 🔴 无 | P3 — 生产部署阶段 |
| 12 | [streaming-llm.md](./streaming-llm.md) | LLM 流式输出 (SSE) | 🔴 无 | P3 — UX 改进项 |
| 13 | [multimodal-agents.md](./multimodal-agents.md) | 多模态 / Schema 对齐 / Agent 工具节点 | 🔴 无 | P3 — 远期扩展 |

## 命名约定

- 单文件聚焦单模块或单主题；跨模块依赖在文末 `## 依赖` 段落标注。
- 每个清单遵循结构：`目标` → `范围` → `子任务（带验收）` → `依赖` → `参考`。
- 子任务粒度向 plan 模板 (`docs/superpowers/plans/...`) 对齐：可直接转 plan 任务。

## 立项流程

1. 选定 todo → 复制内容到新 spec 草稿 `docs/superpowers/specs/YYYY-MM-DD-<topic>.md`。
2. 通过 brainstorming 澄清要求与边界。
3. `superpowers:writing-plans` 落 plan。
4. `superpowers:subagent-driven-development` 或 `executing-plans` 推进。

## 优先级口径

- **P0**：阻塞二期任何工作，先做。
- **P1**：直接影响骨架已声明可跑的链路质量。
- **P2**：上线 / 集成前必须；可在二期内并行。
- **P3**：扩展项，按业务排期。

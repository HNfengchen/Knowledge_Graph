# analysis —— 调用分析采集 / 聚合 / 告警

## 目标

把 LLM 调用 callback 写入 Redis Stream 的事件实时消费成可查询指标，并按 `ALERT_RULES` 触发告警通知。spec §4.4 + 设计方案 §4.4 + §6 alerting。

## 当前状态

- `src/kg_system/llm/callbacks.py:AnalysisCallbackHandler`：已 XADD 事件到 `LLM_STREAM_KEY`（骨架已实现）。
- `src/kg_system/analysis/collector.py`：`StreamCollector.start/stop` OK，`_run` 仅 `await self._stop.wait()`，不读 Stream。
- `src/kg_system/analysis/metrics.py`：`MetricsAggregator.get_qps/get_latency_percentiles/get_daily_cost_usd` 全部 `NotImplementedInSkeleton`。
- `src/kg_system/analysis/alerts.py`：`ALERT_RULES` 静态字典齐全；`evaluate/notify` `NotImplementedInSkeleton`。

## 范围

- **入**：Redis Stream `kg:llm:stream` 中 `AnalysisCallbackHandler` 投递的事件（`{type, model, prompt_tokens, completion_tokens, duration_ms, error?}`）。
- **出**：分桶聚合指标（QPS / 延迟 P50/P95/P99 / 成本 / 错误率）+ 告警事件。
- **不在范围**：可视化前端面板（直接走 `/api/v1/llm/analyze` JSON 即可）。

## 子任务

### Collector

- [ ] **T1：StreamCollector 真正消费**
  - 使用 `XREADGROUP GROUP analysis main BLOCK 1000 COUNT 100 STREAMS kg:llm:stream >`。
  - Group 不存在则 `XGROUP CREATE ... MKSTREAM` 兜底。
  - 验收：模拟写 1000 条事件，全部消费且 ACK。

- [ ] **T2：批量聚合落桶**
  - 按分钟桶 (`bucket = ts // 60`) 把指标累加到 Redis Hash：`kg:metrics:{bucket}` 字段 `count, total_duration, total_prompt_tokens, total_completion_tokens, errors`。
  - 同步维护延迟样本：`kg:latency:{bucket}` 用 `ZADD ts duration` 存近似分布（或 t-digest，骨架先 ZSet）。
  - TTL = 7 天。
  - 验收：单元测试 60s 内 100 条事件聚合为 1 个桶，字段值正确。

- [ ] **T3：消费失败重试**
  - 抛错事件丢进 PEL；定期 `XPENDING` + `XCLAIM` 处理超过 30s 的滞留消息。
  - 验收：人为让聚合一次报错，第二轮被 reclaim 成功。

### Metrics

- [ ] **T4：MetricsAggregator.get_qps**
  - 取 `now - window_seconds` 内的 bucket Hash 求 `sum(count) / window`。
  - 验收：与采集端一致性偏差 ≤ 1%。

- [ ] **T5：MetricsAggregator.get_latency_percentiles**
  - 合并窗口内 ZSet，`ZRANGEBYSCORE` 取分布；P50/P95/P99 用排序近似。
  - 大窗口走 t-digest（备选 `tdigest` lib）。
  - 验收：与离线 numpy.percentile 偏差 < 5%。

- [ ] **T6：MetricsAggregator.get_daily_cost_usd**
  - 按 `model` 拉 token 数 × `LLM_PRICING_TABLE` 计价（配置在 settings 或独立 `llm/pricing.py`）。
  - 验收：手算 vs 函数返回 1e-6 内一致。

### Alerts

- [ ] **T7：AlertManager.evaluate**
  - 用 `metrics`（字典）按 `ALERT_RULES["condition"]` DSL 解析（先用 `simpleeval`，限制可用函数）。
  - 评估为真则构造 `Alert(name, severity, channels, ts, payload)`。
  - 验收：4 条规则对应 4 个 fixture metrics 全部触发。

- [ ] **T8：AlertManager.notify**
  - 渠道适配：`log` 直接写 logger.warning；`webhook` POST `ALERT_WEBHOOK_URL`；`email` 走 SMTP（先 stub），`sms` 先 stub。
  - 失败仅 logger.error，不阻塞主流程。
  - 验收：mock httpx，命中 webhook payload schema。

- [ ] **T9：调度器**
  - 后台 task 每 `ALERT_EVAL_INTERVAL`（默认 30s）跑一次 `evaluate → notify`。
  - 在 `main.py` lifespan 中 start/stop。
  - 验收：日志能看到周期触发。

### 可观测性

- [ ] **T10：自身 metrics**
  - Collector 自身消费速率 / lag / dead-letter 数量推一份到 `kg:metrics:meta:{bucket}`。
  - 验收：lag 持续上涨可被 `service_down` 规则间接观测。

## 依赖

- 与 [api-analysis.md](./api-analysis.md) 配合：`/api/v1/llm/analyze` 直接读 `MetricsAggregator`。
- 与 [llm-cache.md](./llm-cache.md) 共用 `cache_event` 同 Stream（约定 `type=cache_*`）。
- Redis Stream 名常量已在 `core/constants.py`。

## 参考

- spec §4.4、§6.1 告警规则；§5.3 `analysis/{collector,metrics,alerts}.py`。
- 设计方案 §4.4。

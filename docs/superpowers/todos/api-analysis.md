# api/analysis —— `/api/v1/llm/analyze` 落地

## 目标

把 [analysis.md](./analysis.md) 中 `MetricsAggregator` 的输出通过 HTTP 暴露：`GET /api/v1/llm/analyze?window_seconds=...`。spec §4.4。

## 当前状态

`src/kg_system/api/v1/analysis.py`：
- `AnalyzeData{qps, avg_latency_ms, p99_latency_ms, error_rate, daily_cost_usd}` Schema 已定义。
- 受 `require_admin` 守护（X-Admin-Token 比较）。
- 主体 `raise NotImplementedInSkeleton()`。

## 范围

- **入**：`window_seconds` (60..86400, default 300)。
- **出**：`ApiResponse[AnalyzeData]`。
- **不在范围**：历史趋势返回时序数组（首期只返回单值聚合）；告警查询接口（独立 endpoint，二期）。

## 子任务

- [ ] **T1：依赖注入**
  - `get_metrics_aggregator(redis: RedisClient = Depends(get_redis)) -> MetricsAggregator`。
  - 验收：单例缓存 + Redis 连接复用。

- [ ] **T2：endpoint 主体**
  - 并发 `asyncio.gather`：`get_qps(window_seconds)`、`get_latency_percentiles(window_seconds)`、`get_error_rate(window_seconds)`、`get_daily_cost_usd()`。
  - 装配 `AnalyzeData(qps=..., avg_latency_ms=p["p50"], p99_latency_ms=p["p99"], error_rate=..., daily_cost_usd=...)`。
  - 验收：3 个聚合函数被并发调用而非串行（用 `pytest-asyncio` + spy 验证）。

- [ ] **T3：error_rate 新增 metrics 方法**
  - `MetricsAggregator.get_error_rate(window_seconds) -> float`：从 `kg:metrics:{bucket}` Hash 字段 `errors / count`。
  - 与 [analysis.md](./analysis.md) T2 桶 schema 对齐。

- [ ] **T4：参数边界**
  - `window_seconds % 60 != 0` 时向上对齐到分钟，避免最后一桶半边裁剪导致抖动。
  - 验收：`window_seconds=305` 实际取 360s 范围。

- [ ] **T5：缓存**
  - 同一 `window_seconds` 5s 内重复请求走内存缓存（避免压垮 Redis）。
  - 验收：5s 内 100 次请求只触发 1 次 Redis 调用。

- [ ] **T6：扩展 endpoint（可选，本期 P3）**
  - `GET /api/v1/llm/analyze/timeseries?bucket=60s&from=...&to=...` 返回每桶数组。
  - 不在本期实现，但保留 schema：`{ts, qps, p99}` 列表。

## 依赖

- [analysis.md](./analysis.md) T4–T6 必须先就绪。
- `core/config.py` 的 `ADMIN_TOKEN` 必须在生产环境注入（开发态可空，但 endpoint 401）。

## 参考

- spec §4.4、§5.3 `api/v1/analysis.py`。
- 设计方案 §4.4。

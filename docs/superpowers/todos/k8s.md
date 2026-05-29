# k8s —— K8s manifests / HPA / StatefulSet

## 目标

把 docker-compose 描述的拓扑迁到 Kubernetes，支持横向扩缩、滚动更新、持久化。骨架交付 docker-compose 即停，本 todo 是生产部署阶段的工作清单。

## 当前状态

- `docker-compose.yml` OK：4 服务（api / neo4j / redis / postgres）+ healthcheck。
- 仓内无 `deploy/` / `k8s/` / `helm/` 目录。
- 无 Image build 流水线（仅 `python -m kg_system` 入口）。

## 范围

- **入**：当前项目的运行时拓扑。
- **出**：`deploy/k8s/` 下的 Helm chart 或 kustomize overlays，能 `helm install` 起整套环境。
- **不在范围**：多 region；service mesh；多租户隔离。

## 子任务

### 镜像

- [ ] **T1：Dockerfile**
  - 多阶段：`python:3.12-slim` builder（pip install）→ runtime（非 root user，COPY src + prompts + frontend）。
  - 入口：`CMD ["python", "-m", "kg_system"]`。
  - 验收：镜像大小 < 350MB；trivy 扫无 high CVE。

- [ ] **T2：CI 推送**
  - GitHub Actions：tag push 时构建 + push GHCR；语义化版本号。
  - 验收：`ghcr.io/<org>/kg-system:vX.Y.Z` 可拉取。

### 部署

- [ ] **T3：Helm chart 骨架**
  - `deploy/helm/kg-system/{Chart.yaml,values.yaml,templates/}`。
  - `values.yaml` 默认值：副本数、资源 limits、镜像 tag、env、secret refs。

- [ ] **T4：API Deployment + HPA**
  - Deployment：`replicas={{ .Values.api.replicas }}` 默认 2，`readinessProbe: GET /health`，`livenessProbe: GET /health`。
  - HPA：CPU 70% / 内存 75%，min 2 / max 10。
  - 验收：压测触发扩容；副本上下线无 5xx。

- [ ] **T5：Neo4j StatefulSet**
  - StatefulSet 单实例（社区版）+ PVC 100Gi（StorageClass 可配）。
  - 用官方 chart 子依赖更稳：`bitnami/neo4j` 或 `neo4j-helm-charts`。
  - Service 暴露 7687/7474（仅 ClusterIP）。
  - 验收：Pod 重启数据保留。

- [ ] **T6：Redis**
  - 主从 + Sentinel（`bitnami/redis`），3 副本。
  - PVC 10Gi，appendonly yes。
  - 验收：主切换不影响 Stream 消费（kg_system 端有 reconnect）。

- [ ] **T7：Postgres**
  - `bitnami/postgresql` 或 CloudNativePG operator。
  - 主从 + WAL 备份到 S3。
  - 验收：`pg_dump` 可在 S3 找到。

### 配置

- [ ] **T8：Secret + ConfigMap**
  - Secret：`OPENAI_API_KEY`、`JWT_SECRET_KEY`、`ADMIN_TOKEN`、`EXTERNAL_API_KEY`、DB 密码。
  - ConfigMap：非敏感 env（`LOG_LEVEL`、各种 `*_THRESHOLD`、`REASONING_*`）。
  - 用 `external-secrets` operator 对接 Vault / AWS SM。

- [ ] **T9：Ingress**
  - `nginx-ingress` 或 `traefik`：`/api/v1/*` → api Service；`/health` 公开。
  - TLS：cert-manager Let's Encrypt。
  - 验收：`curl https://kg.example.com/health` 200。

### 可观测

- [ ] **T10：Prometheus + Grafana**
  - api ServiceMonitor 抓 `/metrics`（需先实现 prometheus exporter，二期 metrics 模块出口）。
  - Grafana 看板：QPS / P99 / Cache hit / Neo4j heap / Redis memory。

- [ ] **T11：Loki / OpenTelemetry**
  - structlog JSON 日志直接被 Loki 抓。
  - 接 OTel：`opentelemetry-instrumentation-fastapi`。

### 安全

- [ ] **T12：NetworkPolicy**
  - api 只允许 ingress 来自 ingress namespace；neo4j / redis / postgres 只允许 api ns。
  - 验收：`kubectl exec` 任意其他 pod ping 这些服务被拒。

- [ ] **T13：PodSecurity**
  - `runAsNonRoot: true`、`readOnlyRootFilesystem: true`（除 tmp）、`allowPrivilegeEscalation: false`、`drop ALL` capabilities。

## 依赖

- 镜像 → CI/CD 通路。
- 二期 metrics 模块需先实现 Prometheus exporter（[analysis.md](./analysis.md) T10 之后）。
- [tests.md](./tests.md) 的 e2e 在 K8s 集群可继续跑。

## 参考

- spec §1 部署形态；§9 非目标。
- 设计方案 §10（运维与扩展）。

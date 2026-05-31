# Kubernetes Deployment — Design Spec

## Motivation

Replace docker-compose-based local deployment with a production-grade Kubernetes Helm chart, enabling scalable, self-healing deployment.

## Scope

- Helm chart for the `kg-api` application
- Readiness probe for service dependency checking
- ConfigMap-driven configuration
- NOT managing Neo4j/Redis/Postgres inside the chart (users bring their own or add as subcharts)

## Architecture

```
Helm install → ConfigMap (env vars) → Deployment (api container) → Service (ClusterIP)
                                                                   → Ingress (optional)
                                                                   → HPA (optional)
```

## Components

### `deploy/helm/Chart.yaml`

```yaml
apiVersion: v2
name: knowledge-graph
description: Knowledge Graph System API
type: application
version: 0.1.0
appVersion: "0.1.0"
```

### `deploy/helm/values.yaml`

All configuration in one place. Key sections:
- `image`: repository, tag, pullPolicy
- `replicaCount`: default 1
- `config`: FLATTENED env vars (all APP_*, JWT_*, etc. from Settings)
- `neo4j`, `redis`, `postgres`: connection params
- `service`: type (ClusterIP), port
- `ingress`: enabled, host, tls
- `resources`: requests/limits (cpu/memory)
- `hpa`: enabled, minReplicas, maxReplicas, targetCPUUtilizationPercentage
- `pdb`: enabled, minAvailable

### `deploy/helm/templates/_helpers.tpl`

Standard helpers: `knowledge-graph.fullname`, `knowledge-graph.labels`, `knowledge-graph.selectorLabels`

### `deploy/helm/templates/configmap.yaml`

Renders all config values as a ConfigMap. Each key mirrors the env var name (e.g., `APP_ENV`, `NEO4J_URI`, `JWT_SECRET_KEY`). Secrets (passwords, keys) should be set via separate Secret or direct env in deployment.

### `deploy/helm/templates/deployment.yaml`

Standard Deployment with:
- `replicas: {{ .Values.replicaCount }}`
- Container port 8000
- Env from ConfigMap (configRef) + explicit Secret refs for passwords
- Liveness probe: `GET /health` (initialDelaySeconds: 10, periodSeconds: 15)
- Readiness probe: `GET /health/ready` (initialDelaySeconds: 5, periodSeconds: 10)
- Resource requests/limits
- Pod anti-affinity if replicas > 1

### `deploy/helm/templates/service.yaml`

Standard ClusterIP service targeting port 8000.

### `deploy/helm/templates/ingress.yaml`

Conditional (`{{ if .Values.ingress.enabled }}`):
- Host-based routing
- TLS support
- Annotations configurable

### `deploy/helm/templates/hpa.yaml`

Conditional HorizontalPodAutoscaler with CPU target.

### `deploy/helm/templates/pdb.yaml`

Conditional PodDisruptionBudget.

## Health Check Enhancements

### `GET /health` (existing — liveness)

Keep as-is: returns 200 + `{"status":"ok"}`. No dependency checks (liveness should not depend on downstream services).

### `GET /health/ready` (new — readiness)

Check connectivity to all three dependencies:
1. Redis ping (via `redis_client.get_client().ping()`)
2. Neo4j ping (via `neo4j_client.execute_cypher("RETURN 1")`)
3. Postgres ping (via `postgres_client.fetchrow("SELECT 1")`)

Return 200 if all available, 503 if any fail. Include per-service status in body.

## Non-goals

- Managing stateful services (Neo4j/Redis/Postgres) inside chart
- Service Mesh (Istio/Linkerd) integration
- Canary / blue-green deployment patterns
- External DNS / cert-manager automation
- Monitoring stack (Prometheus/Grafana) — covered separately if needed

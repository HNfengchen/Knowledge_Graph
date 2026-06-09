# Kubernetes Deployment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Helm chart for the kg-api application and add a readiness health endpoint.

**Architecture:** Helm chart in `deploy/helm/` with templates for Deployment, Service, ConfigMap, optional Ingress/HPA/PDB. Readiness probe at `/health/ready` checks Neo4j/Redis/Postgres connectivity.

**Tech Stack:** Helm v3, Kubernetes manifests (YAML), FastAPI (health endpoint)

---

### Task 1: Create Helm chart skeleton

**Files:**
- Create: `deploy/helm/Chart.yaml`
- Create: `deploy/helm/values.yaml`

- [ ] **Create `deploy/helm/Chart.yaml`**

```yaml
apiVersion: v2
name: knowledge-graph
description: Knowledge Graph System API
type: application
version: 0.1.0
appVersion: "0.1.0"
keywords:
  - knowledge-graph
  - neo4j
  - llm
```

- [ ] **Create `deploy/helm/values.yaml`**

```yaml
# -- Number of replicas
replicaCount: 1

image:
  repository: kg-api
  tag: latest
  pullPolicy: IfNotPresent

imagePullSecrets: []

nameOverride: ""
fullnameOverride: ""

config:
  APP_ENV: production
  APP_DEBUG: "false"
  APP_HOST: "0.0.0.0"
  APP_PORT: "8000"
  LOG_LEVEL: INFO
  LOG_FORMAT: json
  TEXT_CHUNK_SIZE: "1000"
  TEXT_CHUNK_OVERLAP: "200"
  TEXT_MAX_LENGTH: "10000"
  ENTITY_TYPES: "Person,Organization,Location,Event,Concept"
  ENTITY_SIMILARITY_THRESHOLD: "0.85"
  RELATION_TYPES: "RELATED_TO,HAS_PROPERTY,PART_OF,WORKS_FOR,LOCATED_IN"
  RELATION_SIMILARITY_THRESHOLD: "0.80"
  EMBEDDING_MODEL: text-embedding-3-small
  EMBEDDING_DIMENSIONS: "1536"
  EMBEDDING_BATCH_SIZE: "100"
  REASONING_MAX_STEPS: "5"
  REASONING_SUBGRAPH_DEPTH: "3"
  REASONING_SUBGRAPH_MAX_NODES: "100"
  REASONING_TEMPERATURE: "0.3"
  ALERT_ENABLED: "true"
  ALERT_CHECK_INTERVAL: "60"
  SEMANTIC_CACHE_ENABLED: "true"
  SEMANTIC_CACHE_SIMILARITY_THRESHOLD: "0.95"
  SEMANTIC_CACHE_MAX_SIZE: "10000"
  SEMANTIC_CACHE_TTL: "86400"
  CORS_ORIGINS: "http://localhost:3000"
  CORS_ALLOW_CREDENTIALS: "true"
  ADMIN_USERNAME: admin

neo4j:
  uri: bolt://neo4j:7687
  user: neo4j
  database: neo4j
  maxConnectionPoolSize: "50"
  connectionTimeout: "30"

redis:
  host: redis
  port: "6379"
  db: "0"
  ssl: "false"
  keyPrefix: "kg:"
  cacheTtl: "3600"

postgres:
  host: postgres
  port: "5432"
  user: kg_user
  database: knowledge_graph
  poolSize: "10"

jwt:
  algorithm: HS256
  accessTokenExpireMinutes: "1440"

serviceAccount:
  create: false
  annotations: {}
  name: ""

service:
  type: ClusterIP
  port: 8000

ingress:
  enabled: false
  className: ""
  annotations: {}
  hosts:
    - host: kg-api.local
      paths:
        - path: /
          pathType: Prefix
  tls: []

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 256Mi

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80

podDisruptionBudget:
  enabled: false
  minAvailable: 1

nodeSelector: {}

tolerations: []

affinity: {}
```

- [ ] **Commit**

```bash
git add deploy/helm/Chart.yaml deploy/helm/values.yaml
git commit -m "feat(k8s): add Helm chart skeleton with Chart.yaml and values.yaml"
```

---

### Task 2: Create _helpers.tpl

**Files:**
- Create: `deploy/helm/templates/_helpers.tpl`

- [ ] **Create `deploy/helm/templates/_helpers.tpl`**

```yaml
{{- define "knowledge-graph.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "knowledge-graph.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "knowledge-graph.labels" -}}
helm.sh/chart: {{ include "knowledge-graph.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "knowledge-graph.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "knowledge-graph.selectorLabels" -}}
app.kubernetes.io/name: {{ include "knowledge-graph.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/_helpers.tpl
git commit -m "feat(k8s): add Helm template helpers"
```

---

### Task 3: Create ConfigMap template

**Files:**
- Create: `deploy/helm/templates/configmap.yaml`

- [ ] **Create `deploy/helm/templates/configmap.yaml`**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "knowledge-graph.fullname" . }}-config
  labels:
    {{- include "knowledge-graph.labels" . | nindent 4 }}
data:
  APP_ENV: {{ .Values.config.APP_ENV | quote }}
  APP_DEBUG: {{ .Values.config.APP_DEBUG | quote }}
  APP_HOST: {{ .Values.config.APP_HOST | quote }}
  APP_PORT: {{ .Values.config.APP_PORT | quote }}
  LOG_LEVEL: {{ .Values.config.LOG_LEVEL | quote }}
  LOG_FORMAT: {{ .Values.config.LOG_FORMAT | quote }}
  TEXT_CHUNK_SIZE: {{ .Values.config.TEXT_CHUNK_SIZE | quote }}
  TEXT_CHUNK_OVERLAP: {{ .Values.config.TEXT_CHUNK_OVERLAP | quote }}
  TEXT_MAX_LENGTH: {{ .Values.config.TEXT_MAX_LENGTH | quote }}
  ENTITY_TYPES: {{ .Values.config.ENTITY_TYPES | quote }}
  ENTITY_SIMILARITY_THRESHOLD: {{ .Values.config.ENTITY_SIMILARITY_THRESHOLD | quote }}
  RELATION_TYPES: {{ .Values.config.RELATION_TYPES | quote }}
  RELATION_SIMILARITY_THRESHOLD: {{ .Values.config.RELATION_SIMILARITY_THRESHOLD | quote }}
  EMBEDDING_MODEL: {{ .Values.config.EMBEDDING_MODEL | quote }}
  EMBEDDING_DIMENSIONS: {{ .Values.config.EMBEDDING_DIMENSIONS | quote }}
  EMBEDDING_BATCH_SIZE: {{ .Values.config.EMBEDDING_BATCH_SIZE | quote }}
  REASONING_MAX_STEPS: {{ .Values.config.REASONING_MAX_STEPS | quote }}
  REASONING_SUBGRAPH_DEPTH: {{ .Values.config.REASONING_SUBGRAPH_DEPTH | quote }}
  REASONING_SUBGRAPH_MAX_NODES: {{ .Values.config.REASONING_SUBGRAPH_MAX_NODES | quote }}
  REASONING_TEMPERATURE: {{ .Values.config.REASONING_TEMPERATURE | quote }}
  ALERT_ENABLED: {{ .Values.config.ALERT_ENABLED | quote }}
  ALERT_CHECK_INTERVAL: {{ .Values.config.ALERT_CHECK_INTERVAL | quote }}
  SEMANTIC_CACHE_ENABLED: {{ .Values.config.SEMANTIC_CACHE_ENABLED | quote }}
  SEMANTIC_CACHE_SIMILARITY_THRESHOLD: {{ .Values.config.SEMANTIC_CACHE_SIMILARITY_THRESHOLD | quote }}
  SEMANTIC_CACHE_MAX_SIZE: {{ .Values.config.SEMANTIC_CACHE_MAX_SIZE | quote }}
  SEMANTIC_CACHE_TTL: {{ .Values.config.SEMANTIC_CACHE_TTL | quote }}
  CORS_ORIGINS: {{ .Values.config.CORS_ORIGINS | quote }}
  CORS_ALLOW_CREDENTIALS: {{ .Values.config.CORS_ALLOW_CREDENTIALS | quote }}
  ADMIN_USERNAME: {{ .Values.config.ADMIN_USERNAME | quote }}
  NEO4J_URI: {{ .Values.neo4j.uri | quote }}
  NEO4J_USER: {{ .Values.neo4j.user | quote }}
  NEO4J_DATABASE: {{ .Values.neo4j.database | quote }}
  NEO4J_MAX_CONNECTION_POOL_SIZE: {{ .Values.neo4j.maxConnectionPoolSize | quote }}
  NEO4J_CONNECTION_TIMEOUT: {{ .Values.neo4j.connectionTimeout | quote }}
  REDIS_HOST: {{ .Values.redis.host | quote }}
  REDIS_PORT: {{ .Values.redis.port | quote }}
  REDIS_DB: {{ .Values.redis.db | quote }}
  REDIS_SSL: {{ .Values.redis.ssl | quote }}
  REDIS_KEY_PREFIX: {{ .Values.redis.keyPrefix | quote }}
  REDIS_CACHE_TTL: {{ .Values.redis.cacheTtl | quote }}
  POSTGRES_HOST: {{ .Values.postgres.host | quote }}
  POSTGRES_PORT: {{ .Values.postgres.port | quote }}
  POSTGRES_USER: {{ .Values.postgres.user | quote }}
  POSTGRES_DATABASE: {{ .Values.postgres.database | quote }}
  POSTGRES_POOL_SIZE: {{ .Values.postgres.poolSize | quote }}
  JWT_ALGORITHM: {{ .Values.jwt.algorithm | quote }}
  JWT_ACCESS_TOKEN_EXPIRE_MINUTES: {{ .Values.jwt.accessTokenExpireMinutes | quote }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/configmap.yaml
git commit -m "feat(k8s): add ConfigMap template with all app config"
```

---

### Task 4: Create Deployment template

**Files:**
- Create: `deploy/helm/templates/deployment.yaml`

- [ ] **Create `deploy/helm/templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "knowledge-graph.fullname" . }}
  labels:
    {{- include "knowledge-graph.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "knowledge-graph.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      {{- with .Values.podAnnotations }}
      annotations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      labels:
        {{- include "knowledge-graph.labels" . | nindent 8 }}
    spec:
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      serviceAccountName: {{ include "knowledge-graph.serviceAccountName" . }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          envFrom:
            - configMapRef:
                name: {{ include "knowledge-graph.fullname" . }}-config
          env:
            - name: NEO4J_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "knowledge-graph.fullname" . }}-secrets
                  key: neo4j-password
                  optional: true
            - name: REDIS_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "knowledge-graph.fullname" . }}-secrets
                  key: redis-password
                  optional: true
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "knowledge-graph.fullname" . }}-secrets
                  key: postgres-password
                  optional: true
            - name: JWT_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "knowledge-graph.fullname" . }}-secrets
                  key: jwt-secret-key
                  optional: true
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "knowledge-graph.fullname" . }}-secrets
                  key: openai-api-key
                  optional: true
            - name: ADMIN_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "knowledge-graph.fullname" . }}-secrets
                  key: admin-password
                  optional: true
          ports:
            - name: http
              containerPort: 8000
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 5
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health/ready
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
      {{- end }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/deployment.yaml
git commit -m "feat(k8s): add Deployment template with probes and secret refs"
```

---

### Task 5: Create Service template

**Files:**
- Create: `deploy/helm/templates/service.yaml`

- [ ] **Create `deploy/helm/templates/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "knowledge-graph.fullname" . }}
  labels:
    {{- include "knowledge-graph.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "knowledge-graph.selectorLabels" . | nindent 4 }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/service.yaml
git commit -m "feat(k8s): add Service template (ClusterIP)"
```

---

### Task 6: Create optional Ingress template

**Files:**
- Create: `deploy/helm/templates/ingress.yaml`

- [ ] **Create `deploy/helm/templates/ingress.yaml`**

```yaml
{{- if .Values.ingress.enabled -}}
{{- $fullName := include "knowledge-graph.fullname" . -}}
{{- $svcPort := .Values.service.port -}}
{{- if and .Values.ingress.className (not (semverCompare ">=1.18-0" .Capabilities.KubeVersion.GitVersion)) }}
  {{- if not (hasKey .Values.ingress.annotations "kubernetes.io/ingress.class") }}
  {{- $_ := set .Values.ingress.annotations "kubernetes.io/ingress.class" .Values.ingress.className }}
  {{- end }}
{{- end }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ $fullName }}
  labels:
    {{- include "knowledge-graph.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if and .Values.ingress.className (semverCompare ">=1.18-0" .Capabilities.KubeVersion.GitVersion) }}
  ingressClassName: {{ .Values.ingress.className }}
  {{- end }}
  {{- if .Values.ingress.tls }}
  tls:
    {{- range .Values.ingress.tls }}
    - hosts:
        {{- range .hosts }}
        - {{ . | quote }}
        {{- end }}
      secretName: {{ .secretName }}
    {{- end }}
  {{- end }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          {{- range .paths }}
          - path: {{ .path }}
            pathType: {{ .pathType }}
            backend:
              service:
                name: {{ $fullName }}
                port:
                  number: {{ $svcPort }}
          {{- end }}
    {{- end }}
{{- end }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/ingress.yaml
git commit -m "feat(k8s): add optional Ingress template"
```

---

### Task 7: Create optional HPA template

**Files:**
- Create: `deploy/helm/templates/hpa.yaml`

- [ ] **Create `deploy/helm/templates/hpa.yaml`**

```yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "knowledge-graph.fullname" . }}
  labels:
    {{- include "knowledge-graph.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "knowledge-graph.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    {{- if .Values.autoscaling.targetCPUUtilizationPercentage }}
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
    {{- end }}
    {{- if .Values.autoscaling.targetMemoryUtilizationPercentage }}
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetMemoryUtilizationPercentage }}
    {{- end }}
{{- end }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/hpa.yaml
git commit -m "feat(k8s): add optional HPA template"
```

---

### Task 8: Create optional PDB template

**Files:**
- Create: `deploy/helm/templates/pdb.yaml`

- [ ] **Create `deploy/helm/templates/pdb.yaml`**

```yaml
{{- if .Values.podDisruptionBudget.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "knowledge-graph.fullname" . }}
  labels:
    {{- include "knowledge-graph.labels" . | nindent 4 }}
spec:
  {{- if .Values.podDisruptionBudget.minAvailable }}
  minAvailable: {{ .Values.podDisruptionBudget.minAvailable }}
  {{- end }}
  {{- if .Values.podDisruptionBudget.maxUnavailable }}
  maxUnavailable: {{ .Values.podDisruptionBudget.maxUnavailable }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "knowledge-graph.selectorLabels" . | nindent 6 }}
{{- end }}
```

- [ ] **Commit**

```bash
git add deploy/helm/templates/pdb.yaml
git commit -m "feat(k8s): add optional PDB template"
```

---

### Task 9: Add /health/ready endpoint

**Files:**
- Modify: `src/kg_system/main.py`
- Modify: `tests/unit/test_api_middleware.py` (or create separate test)

- [ ] **Add readiness endpoint in `create_app()` in `main.py`**

After the existing `/health` endpoint in `create_app()`, add:

```python
@app.get("/health/ready", response_model=ApiResponse[dict])
async def health_ready(request: Request) -> ApiResponse[dict]:
    state = request.app.state
    statuses: dict[str, str] = {}

    # Check Neo4j
    neo4j: Neo4jClient | None = getattr(state, "neo4j", None)
    if neo4j:
        try:
            await neo4j.execute_cypher("RETURN 1 AS ok")
            statuses["neo4j"] = "ok"
        except Exception:
            statuses["neo4j"] = "unavailable"
    else:
        statuses["neo4j"] = "not_configured"

    # Check Redis
    redis: RedisClient | None = getattr(state, "redis", None)
    if redis:
        try:
            r = redis.get_client()
            await r.ping()
            await r.close()
            statuses["redis"] = "ok"
        except Exception:
            statuses["redis"] = "unavailable"
    else:
        statuses["redis"] = "not_configured"

    # Check Postgres
    postgres: PostgresClient | None = getattr(state, "postgres", None)
    if postgres:
        try:
            await postgres.fetchrow("SELECT 1 AS ok")
            statuses["postgres"] = "ok"
        except Exception:
            statuses["postgres"] = "unavailable"
    else:
        statuses["postgres"] = "not_configured"

    all_ok = all(v == "ok" for v in statuses.values())
    if not all_ok:
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content=ApiResponse(code=503, msg="not ready", data=statuses).model_dump(),
        )
    return ApiResponse(data=statuses)
```

Also add these imports at the top of `main.py` (if not already present):
```python
from fastapi import FastAPI, Request
from kg_system.storage.postgres_client import PostgresClient
```

- [ ] **Add tests**

Add these tests to `tests/unit/test_api_middleware.py`:

```python
@pytest.mark.unit
async def test_health_ready_all_down(client: AsyncClient):
    resp = await client.get("/health/ready")
    assert resp.status_code == 503
    data = resp.json()
    assert data["code"] == 503
    assert "neo4j" in data["data"]


@pytest.mark.unit
async def test_health_liveness_returns_200(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"
```

- [ ] **Run tests**

```bash
python -m pytest tests/ -m unit --no-header --tb=short -x -v
```

Expected: 82 passed (2 new tests)

- [ ] **Commit**

```bash
git add src/kg_system/main.py tests/unit/test_api_middleware.py
git commit -m "feat: add /health/ready readiness probe endpoint"
```

---

### Task 10: Validate Helm chart

**Files:**
- Validate chart

- [ ] **Run Helm lint**

```bash
helm lint deploy/helm/
```

Expected: 0 errors, 0 warnings (or acceptable warnings about optional templates)

- [ ] **Render templates with default values**

```bash
helm template kg-test deploy/helm/ --debug > /dev/null
```

Expected: Success, no template errors

- [ ] **Render templates with ingress enabled**

```bash
helm template kg-test deploy/helm/ --set ingress.enabled=true --set ingress.hosts[0].host=example.com
```

Expected: Ingress resource appears in output

- [ ] **Commit** (if any chart fixes needed)

```bash
git add deploy/helm/
git commit -m "fix(k8s): chart validation fixes"
```

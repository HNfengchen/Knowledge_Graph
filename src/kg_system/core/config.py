from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全部环境配置。字段名与 .env.example 的键一一对应。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 应用基础
    APP_NAME: str = "knowledge-graph-system"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # LLM
    LLM_DEFAULT_PROVIDER: Literal["openai", "anthropic", "local"] = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 4096
    OPENAI_TIMEOUT: int = 60
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_TEMPERATURE: float = 0.7
    ANTHROPIC_MAX_TOKENS: int = 4096
    LOCAL_LLM_BASE_URL: str = "http://localhost:8000/v1"
    LOCAL_LLM_MODEL: str = "qwen2.5-7b-instruct"
    LOCAL_LLM_API_KEY: str = "not-needed"
    LOCAL_LLM_TEMPERATURE: float = 0.7
    LOCAL_LLM_MAX_TOKENS: int = 4096

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MAX_CONNECTION_POOL_SIZE: int = 50
    NEO4J_CONNECTION_TIMEOUT: int = 30

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_SSL: bool = False
    REDIS_DECODE_RESPONSES: bool = True
    REDIS_KEY_PREFIX: str = "kg:"
    REDIS_CACHE_TTL: int = 3600
    REDIS_STREAM_KEY: str = "llm_calls_stream"
    REDIS_METRICS_PREFIX: str = "metrics:"

    # Postgres（骨架未使用）
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "kg_user"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DATABASE: str = "knowledge_graph"
    POSTGRES_POOL_SIZE: int = 10

    # 安全
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    API_KEY_PREFIX: str = "kg-api-"
    API_KEY_HEADER: str = "X-API-Key"
    ADMIN_TOKEN: str = ""
    EXTERNAL_API_KEY: str = ""
    EXTERNAL_API_IP_WHITELIST: str = "127.0.0.1,::1"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "Content-Type,Authorization,X-API-Key"

    # 构建
    TEXT_CHUNK_SIZE: int = 1000
    TEXT_CHUNK_OVERLAP: int = 200
    TEXT_MAX_LENGTH: int = 10000
    ENTITY_EXTRACTION_PROMPT_TEMPLATES: str = "/app/prompts/entity_extraction.txt"
    ENTITY_TYPES: str = "Person,Organization,Location,Event,Concept"
    ENTITY_SIMILARITY_THRESHOLD: float = 0.85
    RELATION_EXTRACTION_PROMPT_TEMPLATES: str = "/app/prompts/relation_extraction.txt"
    RELATION_TYPES: str = "RELATED_TO,HAS_PROPERTY,PART_OF,WORKS_FOR,LOCATED_IN"
    RELATION_SIMILARITY_THRESHOLD: float = 0.80
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_BATCH_SIZE: int = 100

    # 推理
    REASONING_MAX_STEPS: int = 5
    REASONING_SUBGRAPH_DEPTH: int = 3
    REASONING_SUBGRAPH_MAX_NODES: int = 100
    REASONING_TEMPERATURE: float = 0.3

    # 告警
    ALERT_ENABLED: bool = True
    ALERT_CHECK_INTERVAL: int = 60
    ALERT_QPS_THRESHOLD: int = 500
    ALERT_AVG_RESPONSE_TIME_THRESHOLD: int = 5000
    ALERT_P99_RESPONSE_TIME_THRESHOLD: int = 10000
    ALERT_ERROR_RATE_THRESHOLD: float = 0.01
    ALERT_SUCCESS_RATE_THRESHOLD: float = 0.99
    ALERT_LOG_ENABLED: bool = True
    ALERT_WEBHOOK_URL: str = ""
    ALERT_WEBHOOK_TIMEOUT: int = 10
    ALERT_EMAIL_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    ALERT_EMAIL_RECIPIENTS: str = ""

    # 成本
    COST_OPENAI_GPT4O_INPUT: float = 2.50
    COST_OPENAI_GPT4O_OUTPUT: float = 10.00
    COST_OPENAI_GPT4O_MINI_INPUT: float = 0.15
    COST_OPENAI_GPT4O_MINI_OUTPUT: float = 0.60
    COST_ANTHROPIC_CLAUDE35_INPUT: float = 3.00
    COST_ANTHROPIC_CLAUDE35_OUTPUT: float = 15.00
    COST_LOCAL_MODEL_INPUT: float = 0.00
    COST_LOCAL_MODEL_OUTPUT: float = 0.00
    DAILY_BUDGET_USD: float = 100.00
    MONTHLY_BUDGET_USD: float = 2000.00
    BUDGET_ALERT_THRESHOLD: float = 0.80

    # 缓存
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.95
    SEMANTIC_CACHE_MAX_SIZE: int = 10000
    SEMANTIC_CACHE_TTL: int = 86400

    # 前端
    FRONTEND_API_BASE_URL: str = "http://localhost:8000"
    FRONTEND_WS_URL: str = "ws://localhost:8000"
    FRONTEND_DEFAULT_GRAPH_DEPTH: int = 2
    FRONTEND_MAX_GRAPH_NODES: int = 500

    # 日志
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"
    LOG_FILE_ENABLED: bool = False
    LOG_FILE_PATH: str = "/var/log/kg/app.log"
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 5

    # 性能
    HTTP_CONNECTION_POOL_SIZE: int = 100
    HTTP_CONNECTION_TIMEOUT: int = 30
    ASYNC_WORKER_COUNT: int = 4
    ASYNC_TASK_TIMEOUT: int = 300
    CACHE_WARMUP_ENABLED: bool = False
    CACHE_WARMUP_ENTITIES: str = "high_priority_entities.txt"

    # —— 派生属性 ——
    @property
    def entity_types_list(self) -> list[str]:
        return [t.strip() for t in self.ENTITY_TYPES.split(",") if t.strip()]

    @property
    def relation_types_list(self) -> list[str]:
        return [t.strip() for t in self.RELATION_TYPES.split(",") if t.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def external_ip_whitelist(self) -> set[str]:
        return {ip.strip() for ip in self.EXTERNAL_API_IP_WHITELIST.split(",") if ip.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

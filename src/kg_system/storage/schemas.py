from __future__ import annotations

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT entity_name_type_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
]

FULLTEXT_INDEXES: list[str] = [
    "CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS "
    "FOR (e:Entity) ON EACH [e.name, e.description]",
]


def _vector_index_cypher(dim: int) -> str:
    return (
        "CREATE VECTOR INDEX entity_embedding IF NOT EXISTS "
        "FOR (e:Entity) ON e.embedding "
        "OPTIONS { indexConfig: { "
        f"`vector.dimensions`: {dim}, "
        "`vector.similarity_function`: 'cosine' "
        "} }"
    )


async def apply_schema(client: Neo4jClient) -> None:
    """启动时执行。所有语句幂等（IF NOT EXISTS）。"""
    s = get_settings()
    statements = [*CONSTRAINTS, *FULLTEXT_INDEXES, _vector_index_cypher(s.EMBEDDING_DIMENSIONS)]
    for stmt in statements:
        try:
            await client.execute_cypher(stmt)
            log.info("schema_applied", stmt=stmt[:80])
        except Exception as e:
            # 老版本 Neo4j 不支持 vector index 时给 warning，不阻塞启动
            log.warning("schema_stmt_failed", stmt=stmt[:80], error=str(e))

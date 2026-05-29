from __future__ import annotations

from kg_system.core.logging import get_logger
from kg_system.core.models import ExtractedEntity
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


class Disambiguator:
    """实体消歧。骨架阶段：按 (name, type) 完全匹配查现有节点，命中则带回原 props。
    后续可扩展为 fulltext 模糊匹配 + 向量相似度阈值。
    """

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def resolve(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        out: list[ExtractedEntity] = []
        for ent in entities:
            existing = await self._neo4j.find_entity_by_name(ent.name, ent.type)
            if existing is None:
                out.append(ent)
                continue
            merged_props = {**existing.props, **ent.props}
            out.append(
                ExtractedEntity(
                    name=ent.name,
                    type=ent.type,
                    props=merged_props,
                    source_chunk_id=ent.source_chunk_id,
                )
            )
        log.info("disambiguator_resolved", input=len(entities), output=len(out))
        return out

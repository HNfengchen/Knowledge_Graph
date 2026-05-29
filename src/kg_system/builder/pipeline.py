from __future__ import annotations

import uuid

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from kg_system.builder.chunker import chunk_text
from kg_system.builder.disambiguator import Disambiguator
from kg_system.builder.extractor import EntityExtractor, RelationExtractor
from kg_system.core.logging import get_logger
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


class BuildResult(BaseModel):
    doc_id: str
    chunks: int
    entities_upserted: int
    relations_upserted: int


class KGBuildPipeline:
    """文本 → 分块 → 实体 → 关系 → 消歧 → 入库。"""

    def __init__(self, llm: BaseChatModel, neo4j: Neo4jClient) -> None:
        self._llm = llm
        self._neo4j = neo4j
        self._entity_ex = EntityExtractor(llm)
        self._relation_ex = RelationExtractor(llm)
        self._disamb = Disambiguator(neo4j)

    async def run(self, text: str, doc_id: str) -> BuildResult:
        chunks = chunk_text(text)
        log.info("pipeline_chunked", doc_id=doc_id, chunks=len(chunks))

        all_entities = []
        all_relations = []
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}::chunk-{idx}"
            ents = await self._entity_ex.extract(chunk)
            for e in ents:
                e.source_chunk_id = chunk_id
            rels = await self._relation_ex.extract(chunk, ents)
            all_entities.extend(ents)
            all_relations.extend(rels)

        resolved = await self._disamb.resolve(all_entities)
        name_to_id = await self._neo4j.upsert_entities(resolved)
        rel_count = await self._neo4j.upsert_relations(all_relations, name_to_id)

        return BuildResult(
            doc_id=doc_id,
            chunks=len(chunks),
            entities_upserted=len(name_to_id),
            relations_upserted=rel_count,
        )

    @staticmethod
    def gen_doc_id() -> str:
        return f"doc-{uuid.uuid4().hex[:12]}"

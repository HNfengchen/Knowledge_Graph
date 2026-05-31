from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from kg_system.builder.disambiguator import Disambiguator
from kg_system.core.models import ExtractedEntity, GraphNode


class FakeEmbeddingModel:
    async def aembed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class TestDisambiguator:
    """测试 Disambiguator 各分支。"""

    @pytest.fixture
    def neo4j_with_existing(self):
        m = AsyncMock()
        m.find_entity_by_name = AsyncMock(
            side_effect=lambda name, type_: (
                GraphNode(id="n1", name="Alice", type="Person", props={"age": 30})
                if name == "Alice" and type_ == "Person"
                else None
            )
        )
        m.vector_search_entities = AsyncMock(return_value=[])
        m.fulltext_search_entities = AsyncMock(return_value=[])
        return m

    @pytest.fixture
    def neo4j_empty(self):
        m = AsyncMock()
        m.find_entity_by_name = AsyncMock(return_value=None)
        m.vector_search_entities = AsyncMock(return_value=[])
        m.fulltext_search_entities = AsyncMock(return_value=[])
        return m

    async def test_exact_match_resolved(self, neo4j_with_existing):
        d = Disambiguator(neo4j_with_existing, embedding_model=FakeEmbeddingModel())
        entities = [ExtractedEntity(name="Alice", type="Person", props={"new_key": "val"})]
        resolved = await d.resolve(entities)
        assert len(resolved) == 1
        assert resolved[0].name == "Alice"
        assert resolved[0].props.get("age") == 30
        assert resolved[0].props.get("new_key") == "val"

    async def test_new_entity_when_no_match(self, neo4j_empty):
        d = Disambiguator(neo4j_empty, embedding_model=FakeEmbeddingModel())
        entities = [ExtractedEntity(name="Bob", type="Person")]
        resolved = await d.resolve(entities)
        assert len(resolved) == 1
        assert resolved[0].name == "Bob"

    async def test_empty_list(self, neo4j_empty):
        d = Disambiguator(neo4j_empty)
        resolved = await d.resolve([])
        assert resolved == []

    async def test_multiple_entities(self, neo4j_with_existing):
        d = Disambiguator(neo4j_with_existing, embedding_model=FakeEmbeddingModel())
        entities = [
            ExtractedEntity(name="Alice", type="Person"),
            ExtractedEntity(name="Bob", type="Person"),
        ]
        resolved = await d.resolve(entities)
        assert len(resolved) == 2

    async def test_vector_candidate_bind(self, neo4j_empty):
        """测试向量召回找到高相似度候选时绑定。"""
        neo4j_empty.vector_search_entities = AsyncMock(
            return_value=[
                GraphNode(id="n1", name="Alan Turing", type="Person", props={"field": "CS"})
            ]
        )
        d = Disambiguator(neo4j_empty, embedding_model=FakeEmbeddingModel())
        entities = [ExtractedEntity(name="Alan Turing", type="Person")]
        resolved = await d.resolve(entities)
        assert len(resolved) == 1

    async def test_no_vector_returns_original(self, neo4j_empty):
        """即使没有向量索引，也应返回原始实体（退化）。"""
        neo4j_empty.vector_search_entities = AsyncMock(return_value=[])
        d = Disambiguator(neo4j_empty, embedding_model=FakeEmbeddingModel())
        entities = [ExtractedEntity(name="NewEntity", type="Concept")]
        resolved = await d.resolve(entities)
        assert len(resolved) == 1

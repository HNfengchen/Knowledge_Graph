from __future__ import annotations

from typing import Any

import pytest

from kg_system.builder.disambiguator import Disambiguator
from kg_system.builder.extractor import EntityExtractor, RelationExtractor
from kg_system.builder.pipeline import KGBuildPipeline
from kg_system.storage.neo4j_client import Neo4jClient
from tests.fakes.llm import FakeChatModel


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        item.add_marker(pytest.mark.unit)


@pytest.fixture
def fake_llm() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def fake_entity_extractor(fake_llm: FakeChatModel) -> EntityExtractor:
    return EntityExtractor(fake_llm)


@pytest.fixture
def fake_relation_extractor(fake_llm: FakeChatModel) -> RelationExtractor:
    return RelationExtractor(fake_llm)


@pytest.fixture
def fake_neo4j() -> Any:
    """返回一个最简单的 mock Neo4jClient。"""

    class FakeNeo4j:
        async def find_entity_by_name(self, name: str, type_: str) -> dict | None:
            return None

        async def upsert_entities(self, entities: list) -> dict:
            return {e.name: f"id-{e.name}" for e in entities}

        async def upsert_relations(self, relations: list, name_to_id: dict) -> int:
            return len(relations)

    return FakeNeo4j()

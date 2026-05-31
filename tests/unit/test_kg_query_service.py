from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from kg_system.kg_query.service import KGQueryService


@pytest.fixture
def mock_neo4j():
    m = AsyncMock()
    m.match_subgraph = AsyncMock(
        return_value={"nodes": [], "links": [], "center": None}
    )
    return m


class TestKGQueryService:
    async def test_query_subgraph_empty(self, mock_neo4j):
        svc = KGQueryService(mock_neo4j)
        result = await svc.query_subgraph("UnknownEntity", depth=2)
        assert result is not None

    async def test_query_subgraph_passes_depth(self, mock_neo4j):
        svc = KGQueryService(mock_neo4j)
        await svc.query_subgraph("Alice", depth=3)
        mock_neo4j.match_subgraph.assert_called_once_with("Alice", 3, None)

    async def test_query_subgraph_with_relation_types(self, mock_neo4j):
        svc = KGQueryService(mock_neo4j)
        await svc.query_subgraph("Alice", depth=2, relation_types=["WORKS_FOR"])
        mock_neo4j.match_subgraph.assert_called_once_with("Alice", 2, ["WORKS_FOR"])

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kg_system.core.models import (
    ApiResponse,
    ExtractedEntity,
    ExtractedRelation,
    GraphLink,
    GraphNode,
    SubgraphResult,
)


class TestExtractedEntity:
    def test_minimal(self):
        e = ExtractedEntity(name="Alice", type="Person")
        assert e.name == "Alice"
        assert e.type == "Person"
        assert e.props == {}
        assert e.source_chunk_id is None

    def test_with_props(self):
        e = ExtractedEntity(name="Bob", type="Person", props={"age": 30})
        assert e.props == {"age": 30}

    def test_name_required(self):
        with pytest.raises(ValidationError):
            ExtractedEntity(type="Person")  # type: ignore

    def test_type_required(self):
        with pytest.raises(ValidationError):
            ExtractedEntity(name="Charlie")  # type: ignore


class TestExtractedRelation:
    def test_minimal(self):
        r = ExtractedRelation(head="Alice", tail="Bob", relation="WORKS_FOR")
        assert r.head == "Alice"
        assert r.tail == "Bob"
        assert r.relation == "WORKS_FOR"

    def test_all_fields(self):
        r = ExtractedRelation(
            head="A", tail="B", relation="PART_OF", props={"since": 2020}
        )
        assert r.props == {"since": 2020}


class TestGraphNode:
    def test_minimal(self):
        n = GraphNode(id="n1", type="Person", name="Alice")
        assert n.id == "n1"
        assert n.type == "Person"

    def test_with_props(self):
        n = GraphNode(id="n2", type="Org", name="ACME", props={"founded": 1999})
        assert n.props == {"founded": 1999}


class TestGraphLink:
    def test_minimal(self):
        lk = GraphLink(source="n1", target="n2", relation="WORKS_FOR")
        assert lk.source == "n1"
        assert lk.target == "n2"


class TestSubgraphResult:
    def test_empty(self):
        sg = SubgraphResult(nodes=[], links=[])
        assert sg.nodes == []
        assert sg.links == []

    def test_roundtrip(self):
        sg = SubgraphResult(
            nodes=[GraphNode(id="n1", type="Person", name="Alice")],
            links=[GraphLink(source="n1", target="n2", relation="KNOWS")],
        )
        d = sg.model_dump()
        assert d["nodes"][0]["name"] == "Alice"


class TestApiResponse:
    def test_defaults(self):
        r = ApiResponse()
        assert r.code == 200
        assert r.msg == "success"
        assert r.data is None

    def test_with_data(self):
        r = ApiResponse(data={"key": "val"})
        assert r.data == {"key": "val"}

    def test_error(self):
        r = ApiResponse(code=400, msg="bad request")
        assert r.code == 400

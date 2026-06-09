from __future__ import annotations

import json

import pytest

from kg_system.reasoning.streaming import sse_event


@pytest.mark.unit
class TestSseEvent:
    def test_basic_event(self):
        result = sse_event("node_start", node="retrieve")
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "node_start"
        assert data["node"] == "retrieve"

    def test_token_event(self):
        result = sse_event("token", content="hello")
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "token"
        assert data["content"] == "hello"

    def test_complete_event(self):
        result = sse_event("complete", answer="42", trace=["step1"], evidence={"nodes": []})
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "complete"
        assert data["answer"] == "42"
        assert data["trace"] == ["step1"]

    def test_error_event(self):
        result = sse_event("error", message="oops")
        data = json.loads(result[len("data: "):].strip())
        assert data["type"] == "error"
        assert data["message"] == "oops"

    def test_format_ends_with_double_newline(self):
        result = sse_event("test", foo="bar")
        assert result.endswith("\n\n")

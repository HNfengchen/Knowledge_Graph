from __future__ import annotations

import json

import pytest

from kg_system.builder.extractor import _parse_json_strict


class TestParseJsonStrict:
    def test_plain_json(self):
        result = _parse_json_strict('{"entities": []}')
        assert result == {"entities": []}

    def test_with_markdown_fence(self):
        result = _parse_json_strict('```json\n{"entities": []}\n```')
        assert result == {"entities": []}

    def test_with_markdown_fence_no_lang(self):
        result = _parse_json_strict('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_extra_fields(self):
        result = _parse_json_strict('{"entities": [], "extra": "field"}')
        assert result == {"entities": [], "extra": "field"}

    def test_empty_string_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_strict("")

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_strict("{invalid}")

    def test_nested_json(self):
        result = _parse_json_strict('{"a": {"b": [1, 2, 3]}}')
        assert result == {"a": {"b": [1, 2, 3]}}

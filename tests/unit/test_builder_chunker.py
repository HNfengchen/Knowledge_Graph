from __future__ import annotations

from kg_system.builder.chunker import chunk_text


class TestChunkText:
    def test_empty(self):
        assert chunk_text("", chunk_size=100, overlap=20) == []

    def test_short_text(self):
        chunks = chunk_text("hello", chunk_size=100, overlap=20)
        assert chunks == ["hello"]

    def test_exact_size(self):
        text = "a" * 50
        chunks = chunk_text(text, chunk_size=50, overlap=10)
        assert chunks == [text]

    def test_overlap(self):
        text = "hello-world-example-text"
        chunks = chunk_text(text, chunk_size=10, overlap=3)
        assert len(chunks) >= 2
        # verify overlap: last 3 chars of chunk 0 == first 3 chars of chunk 1
        assert chunks[0][-3:] == chunks[1][:3]

    def test_chinese_text(self):
        text = "你好世界这是一个测试文本用于分块"
        chunks = chunk_text(text, chunk_size=6, overlap=2)
        assert len(chunks) >= 2
        assert chunks[0][-2:] == chunks[1][:2]

    def test_no_overlap(self):
        text = "abcdefghijklmnop"
        chunks = chunk_text(text, chunk_size=4, overlap=0)
        assert chunks == ["abcd", "efgh", "ijkl", "mnop"]

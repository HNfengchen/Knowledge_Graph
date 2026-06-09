from __future__ import annotations

import pytest

from kg_system.core.models import IngestResponse, PageOcrResult, PdfResult


@pytest.mark.unit
class TestPageOcrResult:
    def test_minimal(self):
        r = PageOcrResult(page_num=1, text="hello")
        assert r.page_num == 1
        assert r.text == "hello"


@pytest.mark.unit
class TestPdfResult:
    def test_minimal(self):
        r = PdfResult(text="hello", page_count=2, pages=[])
        assert r.text == "hello"
        assert r.page_count == 2

    def test_with_pages(self):
        pages = [PageOcrResult(page_num=1, text="a"), PageOcrResult(page_num=2, text="b")]
        r = PdfResult(text="a\n\nb", page_count=2, pages=pages)
        assert len(r.pages) == 2


@pytest.mark.unit
class TestIngestResponse:
    def test_all_fields(self):
        r = IngestResponse(doc_id="d1", page_count=3, chunks=5, entities_upserted=10, relations_upserted=20)
        assert r.doc_id == "d1"
        assert r.page_count == 3
        assert r.chunks == 5
        assert r.entities_upserted == 10
        assert r.relations_upserted == 20

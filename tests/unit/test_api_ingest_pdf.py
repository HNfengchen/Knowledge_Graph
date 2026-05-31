from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from kg_system.core.models import PageOcrResult, PdfResult


def _bearer_token() -> str:
    return "Bearer " + jwt.encode(
        {"sub": "test"}, "test-secret-key-for-testing-only", algorithm="HS256"
    )


@pytest.fixture
def ingest_app():
    from fastapi import FastAPI
    from kg_system.api.middleware import install_middleware_and_handlers

    _app = FastAPI(lifespan=None)
    install_middleware_and_handlers(_app)

    from kg_system.api.v1.kg import router as kg_router
    _app.include_router(kg_router, prefix="/api/v1")

    _app.state.neo4j = None
    _app.state.redis = None
    _app.state.collector = None
    return _app


@pytest.mark.unit
async def test_ingest_pdf_success(ingest_app):
    pdf_content = b"%PDF-1.4 fake pdf content"
    filename = "test.pdf"

    with (
        patch("kg_system.api.v1.kg.PdfProcessor") as MockProcessor,
        patch("kg_system.api.v1.kg.KGBuildPipeline") as MockPipeline,
    ):
        mock_processor = MagicMock()
        mock_processor.process_pdf.return_value = PdfResult(
            text="extracted text from PDF",
            page_count=2,
            pages=[PageOcrResult(page_num=1, text="page1"), PageOcrResult(page_num=2, text="page2")],
        )
        MockProcessor.return_value = mock_processor

        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(return_value=MagicMock(chunks=3, entities_upserted=5, relations_upserted=8))
        MockPipeline.return_value = mock_pipeline

        transport = ASGITransport(app=ingest_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/kg/ingest-pdf",
                files={"file": (filename, pdf_content, "application/pdf")},
                data={"doc_id": "my-doc"},
                headers={"Authorization": _bearer_token()},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["doc_id"] == "my-doc"
    assert body["data"]["page_count"] == 2
    assert body["data"]["chunks"] == 3
    assert body["data"]["entities_upserted"] == 5
    assert body["data"]["relations_upserted"] == 8


@pytest.mark.unit
async def test_ingest_pdf_unsupported_extension(ingest_app):
    transport = ASGITransport(app=ingest_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/kg/ingest-pdf",
            files={"file": ("doc.txt", b"not a pdf", "text/plain")},
            headers={"Authorization": _bearer_token()},
        )
    assert resp.status_code == 400


@pytest.mark.unit
async def test_ingest_pdf_empty_text(ingest_app):
    with (
        patch("kg_system.api.v1.kg.PdfProcessor") as MockProcessor,
    ):
        mock_processor = MagicMock()
        mock_processor.process_pdf.return_value = PdfResult(
            text="",
            page_count=1,
            pages=[PageOcrResult(page_num=1, text="")],
        )
        MockProcessor.return_value = mock_processor

        transport = ASGITransport(app=ingest_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/kg/ingest-pdf",
                files={"file": ("blank.pdf", b"%PDF", "application/pdf")},
                headers={"Authorization": _bearer_token()},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["chunks"] == 0
    assert body["data"]["entities_upserted"] == 0


@pytest.mark.unit
async def test_ingest_pdf_no_auth(ingest_app):
    transport = ASGITransport(app=ingest_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/kg/ingest-pdf",
            files={"file": ("test.pdf", b"%PDF", "application/pdf")},
        )
        assert resp.status_code == 401

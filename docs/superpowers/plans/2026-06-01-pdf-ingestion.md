# PDF Ingestion & OCR — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PDF file upload → OCR → entity/relation extraction endpoint, reusing the existing text-based builder pipeline.

**Architecture:** PyMuPDF renders each page to PIL Image → pytesseract OCRs each page → combined OCR text feeds into existing KGBuildPipeline (chunk → extract → disambiguate → upsert to Neo4j).

**Tech Stack:** PyMuPDF (fitz), pytesseract, Pillow, FastAPI UploadFile

---

### Task 1: Add dependencies, config, and models

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/kg_system/core/config.py`
- Modify: `src/kg_system/core/models.py`
- Create: `tests/unit/test_core_models_pdf_ingest.py`

- [ ] **Add `pymupdf`, `pytesseract`, `python-multipart` to `pyproject.toml`**

```toml
    # ===== 文件处理 =====
    "pymupdf>=1.24",
    "pytesseract>=0.3",
    "python-multipart>=0.0",
```

Add to the `[project.dependencies]` list, after the `# ===== 存储 =====` section's `"neo4j>=5.25"` line (the actual line may differ; append after the last dependency).

- [ ] **Add config settings to `src/kg_system/core/config.py`**

In the `Settings` class, after `RELATION_TYPES` (or another appropriate location):

```python
# ── 文件处理 ──
MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20 MB
SUPPORTED_FILE_EXTENSIONS: set[str] = {".pdf"}
OCR_LANGUAGE: str = "chi_sim+eng"
```

- [ ] **Add models to `src/kg_system/core/models.py`**

After the `Alert` class (before `model_rebuild`):

```python
# —— PDF 文件提取 ——
class PageOcrResult(BaseModel):
    page_num: int
    text: str


class PdfResult(BaseModel):
    text: str
    page_count: int
    pages: list[PageOcrResult]


class IngestResponse(BaseModel):
    doc_id: str
    page_count: int
    chunks: int
    entities_upserted: int
    relations_upserted: int
```

- [ ] **Create model tests `tests/unit/test_core_models_pdf_ingest.py`**

```python
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
```

- [ ] **Run model tests**

```bash
cd /mnt/e/projects/Knowledge_Graph && PYTHONPATH=src python -m pytest tests/unit/test_core_models_pdf_ingest.py -m unit -v
```

Expected: 4 passed

- [ ] **Commit**

```bash
git add pyproject.toml src/kg_system/core/config.py src/kg_system/core/models.py tests/unit/test_core_models_pdf_ingest.py
git commit -m "feat: add PDF ingestion deps, config, and models"
```

---

### Task 2: Create PdfProcessor with unit tests

**Files:**
- Create: `src/kg_system/builder/pdf_processor.py`
- Create: `tests/unit/test_builder_pdf_processor.py`

- [ ] **Create `src/kg_system/builder/pdf_processor.py`**

```python
from __future__ import annotations

from typing import Any

from kg_system.core.models import PageOcrResult, PdfResult


class PdfProcessor:
    def __init__(self, ocr_lang: str = "chi_sim+eng"):
        self._ocr_lang = ocr_lang

    def pdf_to_images(self, data: bytes) -> list[Any]:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        images: list[Any] = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=300)
            img = pix.tobytes("png")
            from PIL import Image
            import io
            images.append(Image.open(io.BytesIO(img)))
        doc.close()
        return images

    def ocr_images(self, images: list[Any]) -> list[PageOcrResult]:
        import pytesseract

        results: list[PageOcrResult] = []
        for i, img in enumerate(images):
            text = pytesseract.image_to_string(img, lang=self._ocr_lang)
            results.append(PageOcrResult(page_num=i + 1, text=text.strip()))
        return results

    def process_pdf(self, data: bytes) -> PdfResult:
        images = self.pdf_to_images(data)
        pages = self.ocr_images(images)
        combined = "\n\n".join(p.text for p in pages)
        return PdfResult(text=combined, page_count=len(pages), pages=pages)
```

- [ ] **Create unit tests `tests/unit/test_builder_pdf_processor.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from kg_system.builder.pdf_processor import PdfProcessor
from kg_system.core.models import PageOcrResult, PdfResult


@pytest.fixture
def processor():
    return PdfProcessor(ocr_lang="eng")


class TestPdfToImages:
    @patch("fitz.open")
    def test_single_page(self, mock_open, processor):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"png-data"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page
        mock_open.return_value.__enter__.return_value = mock_doc
        mock_open.return_value = mock_doc

        with patch("PIL.Image.open") as mock_img_open:
            mock_img = MagicMock()
            mock_img_open.return_value = mock_img
            images = processor.pdf_to_images(b"fake-pdf-bytes")

        assert len(images) == 1
        mock_doc.load_page.assert_called_once_with(0)
        mock_pix.tobytes.assert_called_once_with("png")


class TestOcrImages:
    @patch("pytesseract.image_to_string", return_value="hello world")
    def test_single_image(self, mock_ocr, processor):
        mock_img = MagicMock()
        results = processor.ocr_images([mock_img])

        assert len(results) == 1
        assert results[0].page_num == 1
        assert results[0].text == "hello world"
        mock_ocr.assert_called_once_with(mock_img, lang="eng")


class TestProcessPdf:
    @patch.object(PdfProcessor, "pdf_to_images")
    @patch.object(PdfProcessor, "ocr_images")
    def test_happy_path(self, mock_ocr, mock_to_images, processor):
        mock_to_images.return_value = [MagicMock(), MagicMock()]
        mock_ocr.return_value = [
            PageOcrResult(page_num=1, text="page1"),
            PageOcrResult(page_num=2, text="page2"),
        ]

        result = processor.process_pdf(b"data")

        assert isinstance(result, PdfResult)
        assert result.page_count == 2
        assert "page1" in result.text
        assert "page2" in result.text
        assert len(result.pages) == 2

    @patch.object(PdfProcessor, "pdf_to_images")
    @patch.object(PdfProcessor, "ocr_images")
    def test_empty_pdf(self, mock_ocr, mock_to_images, processor):
        mock_to_images.return_value = []
        mock_ocr.return_value = []

        result = processor.process_pdf(b"empty")

        assert result.page_count == 0
        assert result.text == ""
```

- [ ] **Run PdfProcessor tests**

```bash
cd /mnt/e/projects/Knowledge_Graph && PYTHONPATH=src python -m pytest tests/unit/test_builder_pdf_processor.py -m unit -v
```

Expected: 7 passed (2 + 1 + 2 + 2 test methods)

- [ ] **Run all unit tests to confirm nothing broken**

```bash
cd /mnt/e/projects/Knowledge_Graph && PYTHONPATH=src python -m pytest tests/ -m unit --no-header -v
```

Expected: 94 passed (90 existing + 4 model + 7 pdf_processor - some may overlap, total approximately 101)

- [ ] **Commit**

```bash
git add src/kg_system/builder/pdf_processor.py tests/unit/test_builder_pdf_processor.py
git commit -m "feat: add PdfProcessor (PyMuPDF + pytesseract)"
```

---

### Task 3: Add /ingest-pdf endpoint with integration test

**Files:**
- Modify: `src/kg_system/api/v1/kg.py`
- Create: `tests/unit/test_api_ingest_pdf.py`

- [ ] **Add /ingest-pdf endpoint to `src/kg_system/api/v1/kg.py`**

Read the current file to understand structure, then add imports and the new endpoint.

Add imports after the existing ones:
```python
import asyncio
from pathlib import Path

from fastapi import File, Form, UploadFile

from kg_system.builder.pdf_processor import PdfProcessor
from kg_system.core.models import IngestResponse, PdfResult
```

Add the endpoint after the existing `build_endpoint`:

```python
@router.post("/ingest-pdf", response_model=ApiResponse[IngestResponse])
async def ingest_pdf(
    file: UploadFile = File(...),
    doc_id: str | None = Form(None),
    neo4j: Neo4jClient = Depends(get_neo4j),
    redis: RedisClient = Depends(get_redis),
    user=Depends(require_user),
):
    s = get_settings()

    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in s.SUPPORTED_FILE_EXTENSIONS:
        from kg_system.core.exceptions import InvalidInput
        raise InvalidInput(f"unsupported file type '{ext}', supported: {s.SUPPORTED_FILE_EXTENSIONS}")

    data = await file.read()
    if len(data) > s.MAX_FILE_SIZE:
        from kg_system.core.exceptions import InvalidInput
        raise InvalidInput(f"file too large, max {s.MAX_FILE_SIZE // (1024*1024)}MB")

    actual_doc_id = doc_id or Path(file.filename).stem

    processor = PdfProcessor(ocr_lang=s.OCR_LANGUAGE)
    pdf_result = processor.process_pdf(data)

    if not pdf_result.text.strip():
        return ApiResponse(
            data=IngestResponse(
                doc_id=actual_doc_id,
                page_count=pdf_result.page_count,
                chunks=0,
                entities_upserted=0,
                relations_upserted=0,
            )
        )

    callback = AnalysisCallbackHandler(redis)
    llm = get_chat_model().with_config({"callbacks": [callback]})
    pipeline = KGBuildPipeline(llm, neo4j)

    try:
        build_result = await asyncio.wait_for(
            pipeline.run(pdf_result.text, actual_doc_id),
            timeout=s.OPENAI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        from kg_system.core.exceptions import LLMTimeoutError
        raise LLMTimeoutError("PDF processing timed out")

    return ApiResponse(
        data=IngestResponse(
            doc_id=actual_doc_id,
            page_count=pdf_result.page_count,
            chunks=build_result.chunks,
            entities_upserted=build_result.entities_upserted,
            relations_upserted=build_result.relations_upserted,
        )
    )
```




- [ ] **Create endpoint tests `tests/unit/test_api_ingest_pdf.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from kg_system.core.models import PdfResult, PageOcrResult


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
        mock_pipeline.run.return_value = MagicMock(chunks=3, entities_upserted=5, relations_upserted=8)
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
    assert resp.status_code == 403
```

- [ ] **Run all tests**

```bash
cd /mnt/e/projects/Knowledge_Graph && PYTHONPATH=src python -m pytest tests/ -m unit --no-header -v
```

Expected: all tests pass (existing 90 + 4 model + 7 pdf_processor + 4 endpoint ≈ 105)

- [ ] **Commit**

```bash
git add src/kg_system/api/v1/kg.py tests/unit/test_api_ingest_pdf.py
git commit -m "feat: add /kg/ingest-pdf endpoint with OCR processing"
```

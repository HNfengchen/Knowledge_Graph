# PDF Ingestion & OCR — Design Spec

## Motivation

Support scanned/image PDF ingestion: upload PDF → OCR → entity/relation extraction → store in Neo4j, reusing the existing text-based builder pipeline.

## Scope

- New endpoint `POST /api/v1/kg/ingest-pdf` accepting `multipart/form-data`
- PDF processor module `builder/pdf_processor.py` (PyMuPDF → pytesseract)
- Config extensions for file size limits and OCR language
- Integration with existing `KGBuildPipeline`
- New dependencies: `pymupdf`, `pytesseract`, `Pillow`, `python-multipart`

## Architecture

```
Client (multipart: file=.pdf, doc_id=optional)
    ↓
POST /api/v1/kg/ingest-pdf
    ↓
[Validate: file size ≤ MAX_FILE_SIZE, extension = .pdf]
    ↓
PDFProcessor.process_pdf(file_bytes, lang=OCR_LANGUAGE)
    ├── PyMuPDF: pdf → list[PIL.Image]
    ├── pytesseract: image → text (per page)
    └── PdfResult { text, page_count }
    ↓
KGBuildPipeline.run(text, doc_id)
    ├── chunk_text() → text chunks
    ├── EntityExtractor.extract(chunk)
    ├── RelationExtractor.extract(chunk, entities)
    ├── Disambiguator.resolve(all_entities)
    └── neo4j.upsert_entities/upsert_relations
    ↓
ApiResponse[IngestResponse] { doc_id, page_count, chunks, entities_upserted, relations_upserted }
```

## Components

### `builder/pdf_processor.py`

```
class PdfProcessor:
    def __init__(self, ocr_lang: str = "chi_sim+eng"):
        self._ocr_lang = ocr_lang

    pdf_to_images(data: bytes) → list[Image.Image]
        PyMuPDF open → page.get_pixmap(dpi=300) → PIL.Image

    ocr_images(images: list[Image.Image]) → str
        pytesseract.image_to_string() per page → join with \n\n

    process_pdf(data: bytes) → PdfResult
        pdf_to_images → ocr_images → PdfResult
```

### `core/models.py` — new models

```python
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

### `core/config.py` — new settings

```python
MAX_FILE_SIZE: int = 20 * 1024 * 1024        # 20 MB
SUPPORTED_FILE_EXTENSIONS: set[str] = {".pdf"}
OCR_LANGUAGE: str = "chi_sim+eng"             # Tesseract language pack(s)
```

### `api/v1/kg.py` — new endpoint

```python
@router.post("/ingest-pdf", response_model=ApiResponse[IngestResponse])
async def ingest_pdf(
    file: UploadFile = File(...),
    doc_id: str | None = Form(None),
    ...
):
    # 1. Validate extension & size
    # 2. Read file bytes
    # 3. PDFProcessor.process_pdf → PdfResult
    # 4. KGBuildPipeline.run(pdf_result.text, doc_id)
    # 5. Return IngestResponse
```

## Non-goals

- Real-time streaming (file processing is inherently batch-oriented)
- Image-only upload (just PDF, extensible later)
- Background task processing (synchronous, timeout-protected)
- Visual LLM (OCR + text pipeline sufficient for current scope)

## Dependencies Added

- `pymupdf` — PDF → image rendering (pure Python, no system deps)
- `pytesseract` — OCR engine wrapper (requires `tesseract-ocr` system package)
- `Pillow` — image format handling (already transitive, now explicit)
- `python-multipart` — FastAPI multipart form parsing

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from kg_system.builder.pdf_processor import PdfProcessor
from kg_system.core.models import PageOcrResult, PdfResult


@pytest.fixture(autouse=True)
def _mock_deps():
    """Pre-populate sys.modules so lazy imports in PdfProcessor work without
    fitz / pytesseract / PIL being installed."""
    import sys

    fitz = MagicMock()
    pytesseract = MagicMock()
    pil = MagicMock()
    Image = MagicMock()
    pil.Image = Image
    sys.modules["fitz"] = fitz
    sys.modules["pytesseract"] = pytesseract
    sys.modules["PIL"] = pil

    yield

    sys.modules.pop("fitz", None)
    sys.modules.pop("pytesseract", None)
    sys.modules.pop("PIL", None)


@pytest.fixture
def processor():
    return PdfProcessor(ocr_lang="eng")


class TestPdfToImages:
    def test_single_page(self, processor):
        import sys

        mock_fitz = sys.modules["fitz"]
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.tobytes.return_value = b"png-data"
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__len__.return_value = 1
        mock_doc.load_page.return_value = mock_page
        mock_fitz.open.return_value = mock_doc

        mock_img_open = MagicMock()
        mock_img = MagicMock()
        mock_img_open.return_value = mock_img
        sys.modules["PIL"].Image.open = mock_img_open

        images = processor.pdf_to_images(b"fake-pdf-bytes")

        assert len(images) == 1
        mock_doc.load_page.assert_called_once_with(0)
        mock_pix.tobytes.assert_called_once_with("png")


class TestOcrImages:
    def test_single_image(self, processor):
        import sys

        mock_pytesseract = sys.modules["pytesseract"]
        mock_pytesseract.image_to_string.return_value = "hello world"

        mock_img = MagicMock()
        results = processor.ocr_images([mock_img])

        assert len(results) == 1
        assert results[0].page_num == 1
        assert results[0].text == "hello world"
        mock_pytesseract.image_to_string.assert_called_once_with(mock_img, lang="eng")


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

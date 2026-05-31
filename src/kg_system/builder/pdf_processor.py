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

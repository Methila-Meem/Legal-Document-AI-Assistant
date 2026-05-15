import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.repositories.documents_repository import DocumentRecord
from app.services.ocr_service import OcrExecutionError, OcrUnavailableError, PaddleOCRService


class DocumentProcessingError(Exception):
    pass


class UnsupportedDocumentTypeError(DocumentProcessingError):
    pass


class OcrEngineMissingError(DocumentProcessingError):
    pass


class OcrProcessingError(DocumentProcessingError):
    pass


@dataclass
class ProcessedPage:
    page_number: int
    source_type: str
    text: str
    text_preview: str
    ocr_confidence: float | None
    is_unclear: bool


@dataclass
class ProcessingResult:
    document_id: str
    status: str
    page_count: int
    pages: list[ProcessedPage]
    warnings: list[str]
    output_path: str


class DocumentProcessingService:
    pdf_text_min_chars = 40

    def __init__(self) -> None:
        self.ocr_service = PaddleOCRService()

    def process(self, document: DocumentRecord) -> ProcessingResult:
        source_path = Path(settings.storage_dir) / "uploads" / document.stored_filename
        if not source_path.exists():
            raise DocumentProcessingError("Uploaded source file was not found.")

        file_type = source_path.suffix.lower().lstrip(".")
        if file_type == "txt":
            pages = [self._process_txt(source_path)]
        elif file_type == "pdf":
            pages = self._process_pdf(source_path)
        elif file_type in {"png", "jpg", "jpeg"}:
            pages = [self._process_image(source_path, page_number=1)]
        else:
            raise UnsupportedDocumentTypeError(f"Unsupported file type: {file_type}")

        warnings = [
            f"Page {page.page_number} has low OCR confidence."
            for page in pages
            if page.is_unclear
        ]
        output_path = self._write_processed_output(document, pages, warnings)

        return ProcessingResult(
            document_id=str(document.id),
            status="processed",
            page_count=len(pages),
            pages=pages,
            warnings=warnings,
            output_path=str(output_path),
        )

    def _process_txt(self, source_path: Path) -> ProcessedPage:
        try:
            text = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = source_path.read_text(encoding="utf-8", errors="replace")

        return ProcessedPage(
            page_number=1,
            source_type="pdf_text",
            text=text,
            text_preview=self._preview(text),
            ocr_confidence=None,
            is_unclear=False,
        )

    def _process_pdf(self, source_path: Path) -> list[ProcessedPage]:
        pages: list[ProcessedPage] = []
        try:
            pdf = fitz.open(source_path)
        except Exception as exc:
            raise DocumentProcessingError("Unable to open PDF document.") from exc

        try:
            for index, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if len(text) >= self.pdf_text_min_chars:
                    pages.append(
                        ProcessedPage(
                            page_number=index,
                            source_type="pdf_text",
                            text=text,
                            text_preview=self._preview(text),
                            ocr_confidence=None,
                            is_unclear=False,
                        )
                    )
                    continue

                image = self._render_pdf_page(page)
                pages.append(self._ocr_image(image, page_number=index))
        finally:
            pdf.close()

        return pages

    def _process_image(self, source_path: Path, page_number: int) -> ProcessedPage:
        try:
            image = Image.open(source_path)
        except UnidentifiedImageError as exc:
            raise DocumentProcessingError("Unable to open image document.") from exc
        return self._ocr_image(image, page_number=page_number)

    def _render_pdf_page(self, page: fitz.Page) -> Image.Image:
        matrix = fitz.Matrix(2, 2)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    def _ocr_image(self, image: Image.Image, page_number: int) -> ProcessedPage:
        try:
            processed_image = self._preprocess_image(image)
        except Exception as exc:
            raise DocumentProcessingError("Image preprocessing failed.") from exc

        try:
            result = self.ocr_service.extract_text(processed_image)
        except OcrUnavailableError as exc:
            raise OcrEngineMissingError(
                "PaddleOCR is unavailable. Install paddleocr and paddlepaddle."
            ) from exc
        except OcrExecutionError as exc:
            raise OcrProcessingError("OCR failed while processing the document.") from exc

        confidence = result.confidence
        is_unclear = (
            confidence is None
            or confidence < settings.ocr_confidence_threshold
            or not result.text.strip()
        )

        return ProcessedPage(
            page_number=page_number,
            source_type="ocr",
            text=result.text,
            text_preview=self._preview(result.text),
            ocr_confidence=confidence,
            is_unclear=is_unclear,
        )

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        rgb_image = image.convert("RGB")
        array = np.array(rgb_image)
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)

        height, width = gray.shape[:2]
        if max(height, width) < 1200:
            gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

        denoised = cv2.medianBlur(gray, 3)
        thresholded = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        return Image.fromarray(thresholded)

    def _write_processed_output(
        self,
        document: DocumentRecord,
        pages: list[ProcessedPage],
        warnings: list[str],
    ) -> Path:
        processed_dir = Path(settings.storage_dir) / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        output_path = processed_dir / f"{document.id}.json"
        payload = {
            "document_id": str(document.id),
            "original_filename": document.original_filename,
            "stored_filename": document.stored_filename,
            "status": "processed",
            "page_count": len(pages),
            "pages": [asdict(page) for page in pages],
            "warnings": warnings,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return output_path

    def _preview(self, text: str, limit: int = 240) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit].rstrip()}..."

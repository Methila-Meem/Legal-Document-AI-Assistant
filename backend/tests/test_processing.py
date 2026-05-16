from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.main import app
from app.repositories.documents_repository import insert_document
from app.services.document_processing_service import OcrEngineMissingError
from app.services.document_processing_service import DocumentProcessingService


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")

    with TestClient(app) as test_client:
        yield test_client


def test_process_txt_document(client: TestClient) -> None:
    upload_dir = settings.resolved_storage_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = "stored-document.txt"
    source_text = "This is a sample legal notice.\nIt contains direct text."
    (upload_dir / stored_filename).write_text(source_text, encoding="utf-8")

    import asyncio

    document = asyncio.run(
        insert_document(
            original_filename="notice.txt",
            stored_filename=stored_filename,
            content_type="text/plain",
            file_size_bytes=len(source_text.encode("utf-8")),
        )
    )

    response = client.post(f"/api/documents/{document.id}/process")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == str(document.id)
    assert payload["status"] == "processed"
    assert payload["page_count"] == 1
    assert payload["pages"][0]["source_type"] == "pdf_text"
    assert payload["pages"][0]["ocr_confidence"] is None
    assert payload["pages"][0]["is_unclear"] is False
    assert "sample legal notice" in payload["pages"][0]["text_preview"]

    output_path = settings.resolved_storage_dir / "processed" / f"{document.id}.json"
    assert output_path.exists()
    assert "This is a sample legal notice." in output_path.read_text(encoding="utf-8")


def test_digital_pdf_processing_does_not_require_ocr(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import fitz

    def fail_if_ocr_is_called(
        self: DocumentProcessingService,
        image: Image.Image,
        page_number: int,
    ):
        raise AssertionError("OCR should not be used for digital PDF text.")

    monkeypatch.setattr(DocumentProcessingService, "_ocr_image", fail_if_ocr_is_called)

    upload_dir = settings.resolved_storage_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = "digital-document.pdf"
    source_path = upload_dir / stored_filename
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Digital PDF text for a synthetic legal notice. " * 3)
    pdf.save(source_path)
    pdf.close()

    document = asyncio.run(
        insert_document(
            original_filename="digital.pdf",
            stored_filename=stored_filename,
            content_type="application/pdf",
            file_size_bytes=source_path.stat().st_size,
        )
    )

    response = client.post(f"/api/documents/{document.id}/process")

    assert response.status_code == 200
    page_payload = response.json()["pages"][0]
    assert page_payload["source_type"] == "pdf_text"
    assert page_payload["ocr_confidence"] is None
    assert page_payload["ocr_engine"] is None


def test_image_preprocessing_falls_back_when_cv2_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.document_processing_service as processing_module

    monkeypatch.setattr(processing_module.cv2, "cvtColor", None, raising=False)
    image = Image.new("RGB", (200, 120), "white")

    processed = DocumentProcessingService()._preprocess_image(image)

    assert processed.mode == "L"
    assert processed.width == 300
    assert processed.height == 180


def test_ocr_unavailable_returns_diagnostic_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_dir = settings.resolved_storage_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = "stored-image.png"
    image = Image.new("RGB", (120, 80), "white")
    image.save(upload_dir / stored_filename)

    import asyncio

    document = asyncio.run(
        insert_document(
            original_filename="sample.png",
            stored_filename=stored_filename,
            content_type="image/png",
            file_size_bytes=(upload_dir / stored_filename).stat().st_size,
        )
    )

    def fail_ocr(self: DocumentProcessingService, image: Image.Image, page_number: int):
        raise OcrEngineMissingError(
            "OCR is unavailable.",
            {
                "message": "OCR is unavailable.",
                "selected_engine": "easyocr",
                "active_engine": None,
                "fallback_engine": "tesseract",
                "error": "No module named 'easyocr'",
                "hint": "Activate backend/venv and run: pip install -r requirements.txt",
            },
        )

    monkeypatch.setattr(DocumentProcessingService, "_ocr_image", fail_ocr)

    response = client.post(f"/api/documents/{document.id}/process")

    assert response.status_code == 503
    error = response.json()["error"]
    assert "OCR is unavailable" in error["message"]
    assert error["details"]["error"] == "No module named 'easyocr'"
    assert "pip install -r requirements.txt" in error["details"]["hint"]

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.documents_repository import insert_document


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")

    with TestClient(app) as test_client:
        yield test_client


def test_process_txt_document(client: TestClient) -> None:
    upload_dir = Path(settings.storage_dir) / "uploads"
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

    output_path = Path(settings.storage_dir) / "processed" / f"{document.id}.json"
    assert output_path.exists()
    assert "This is a sample legal notice." in output_path.read_text(encoding="utf-8")

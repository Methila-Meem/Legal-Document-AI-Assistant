from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.documents_repository import (
    insert_document,
    replace_document_pages,
    update_document_status,
)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(settings, "github_models_api_key", None)

    with TestClient(app) as test_client:
        yield test_client


def test_extract_fields_rules_fallback(client: TestClient) -> None:
    import asyncio

    document = asyncio.run(
        insert_document(
            original_filename="notice.txt",
            stored_filename="notice.txt",
            content_type="text/plain",
            file_size_bytes=100,
        )
    )
    asyncio.run(
        replace_document_pages(
            document.id,
            [
                {
                    "page_number": 1,
                    "text": (
                        "Notice issued on 2026-03-05. Case No. CIV-2026-7788. "
                        "Between John Smith and ABC Holdings LLC. Amount due is $2,500. "
                        "Mail to 123 Main Street, Springfield."
                    ),
                    "source_type": "pdf_text",
                    "ocr_confidence": None,
                    "is_unclear": False,
                }
            ],
        )
    )
    asyncio.run(update_document_status(document.id, "processed"))

    response = client.post(f"/api/documents/{document.id}/extract-fields")

    assert response.status_code == 200
    payload = response.json()
    fields = payload["structured_fields"]
    assert payload["method"] == "rules"
    assert "GitHub Models API key is not configured" in payload["warnings"][0]
    assert fields["document_type"] == "Notice"
    assert "2026-03-05" in fields["dates"]
    assert "$2,500" in fields["monetary_amounts"]
    assert "CIV-2026-7788" in fields["case_numbers"]
    assert any("123 Main Street" in address for address in fields["addresses"])
    assert "John Smith" in fields["parties"]
    assert "ABC Holdings LLC" in fields["parties"]


def test_extract_fields_requires_processed_document(client: TestClient) -> None:
    import asyncio

    document = asyncio.run(
        insert_document(
            original_filename="draft.txt",
            stored_filename="draft.txt",
            content_type="text/plain",
            file_size_bytes=10,
        )
    )

    response = client.post(f"/api/documents/{document.id}/extract-fields")

    assert response.status_code == 409
    assert "must be processed" in response.json()["error"]["message"]

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    monkeypatch.setattr(settings, "max_upload_size_mb", 25)

    with TestClient(app) as test_client:
        yield test_client


def test_upload_txt_file_stores_document(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("contract.txt", b"Sample legal document text.", "text/plain")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["document_id"]
    assert payload["original_filename"] == "contract.txt"
    assert payload["stored_filename"].endswith(".txt")
    assert payload["file_type"] == "txt"
    assert payload["size_bytes"] == 27
    assert payload["status"] == "uploaded"

    stored_path = Path(settings.storage_dir) / "uploads" / payload["stored_filename"]
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"Sample legal document text."


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/documents/upload",
        files={"file": ("script.exe", b"not allowed", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["error"]["message"]


def test_upload_rejects_file_over_size_limit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("large.txt", b"x", "text/plain")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["error"]["message"]

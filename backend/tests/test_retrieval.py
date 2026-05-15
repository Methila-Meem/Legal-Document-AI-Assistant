from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")

    with TestClient(app) as test_client:
        yield test_client


def test_retrieval_query_rejects_empty_query(client: TestClient) -> None:
    response = client.post(
        "/api/retrieval/query",
        json={"document_id": "1", "query": "   ", "top_k": 6},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"

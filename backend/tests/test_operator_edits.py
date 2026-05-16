from pathlib import Path
import asyncio

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.edit_learning_service import RuleExtractionResult


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")

    with TestClient(app) as test_client:
        yield test_client


async def _create_draft() -> int:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO documents (
                original_filename,
                stored_filename,
                content_type,
                file_size_bytes,
                status
            )
            VALUES ('notice.txt', 'notice.txt', 'text/plain', 10, 'indexed')
            """
        )
        document_id = cursor.lastrowid
        cursor = await db.execute(
            """
            INSERT INTO drafts (document_id, draft_type, content, evidence_json, model_name)
            VALUES (?, 'case_fact_summary', ?, '[]', 'gpt-4o-mini')
            """,
            (document_id, "John failed to pay rent. [E1 p.1]"),
        )
        draft_id = cursor.lastrowid
        await db.commit()
    assert draft_id is not None
    return draft_id


def test_saving_operator_edit_creates_active_learning_rule(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_id = asyncio.run(_create_draft())

    class StubEditLearningService:
        async def extract_rules(
            self,
            *,
            original_draft: str,
            edited_draft: str,
        ) -> RuleExtractionResult:
            return RuleExtractionResult(
                diff_text="-John failed to pay rent.\n+The document states John allegedly failed to pay rent.",
                rules=[
                    {
                        "rule_type": "tone",
                        "rule_text": (
                            "Use cautious legal wording such as 'the document states' "
                            "instead of presenting claims as confirmed facts."
                        ),
                        "example_before": "John failed to pay rent.",
                        "example_after": (
                            "The document states John allegedly failed to pay rent."
                        ),
                    }
                ],
            )

    monkeypatch.setattr(
        "app.routers.drafts.EditLearningService",
        lambda: StubEditLearningService(),
    )

    response = client.post(
        f"/api/drafts/{draft_id}/edits",
        json={
            "edited_draft": (
                "The document states John allegedly failed to pay rent. [E1 p.1]"
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["edit_id"]
    assert payload["draft_id"] == str(draft_id)
    assert payload["message"] == "Operator edit saved and reusable rules extracted."
    assert payload["learned_rules"][0]["rule_type"] == "tone"
    assert payload["learned_rules"][0]["is_active"] is True

    rules_response = client.get("/api/learning-rules")
    assert rules_response.status_code == 200
    rules = rules_response.json()
    assert len(rules) == 1
    assert rules[0]["is_active"] is True
    assert "cautious legal wording" in rules[0]["rule_text"]


def test_saving_empty_operator_edit_returns_422(client: TestClient) -> None:
    draft_id = asyncio.run(_create_draft())

    response = client.post(
        f"/api/drafts/{draft_id}/edits",
        json={"edited_draft": "   "},
    )

    assert response.status_code == 422


def test_saving_edit_for_missing_draft_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/drafts/999/edits",
        json={"edited_draft": "Edited content."},
    )

    assert response.status_code == 404

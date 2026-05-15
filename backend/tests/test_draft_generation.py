from app.models.schemas import EvidenceChunk, EvidenceSource
from app.services.draft_generation_service import DraftGenerationService


def test_case_fact_summary_prompt_enforces_grounding_rules() -> None:
    service = DraftGenerationService()
    evidence = [
        EvidenceChunk(
            chunk_id="1",
            document_id="7",
            page_number=2,
            text="ABC Holdings LLC sent notice to John Smith on 2026-03-05.",
            relevance_score=0.91,
            source=EvidenceSource(
                filename="notice.pdf",
                source_type="ocr",
                ocr_confidence=0.52,
            ),
        )
    ]

    _, user_prompt = service.build_case_fact_summary_prompt(
        evidence=evidence,
        learning_rules=[
            {
                "rule_name": "Tone",
                "rule_description": "Use concise neutral wording.",
            }
        ],
    )

    assert "Use only the provided evidence" in user_prompt
    assert "Every factual claim must include a source reference" in user_prompt
    assert 'write "Not found in the provided documents."' in user_prompt
    assert "Do not provide legal advice" in user_prompt
    assert "# Case Fact Summary" in user_prompt
    assert "[E1 p.2]" in user_prompt
    assert "OCR warning" in user_prompt
    assert "Use concise neutral wording" in user_prompt

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
                    "rule_type": "tone",
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
    assert "Apply these operator-learned drafting preferences" in user_prompt
    assert "Tone:" in user_prompt
    assert "Use concise neutral wording" in user_prompt


def test_learning_rules_are_kept_concise_in_prompt() -> None:
    service = DraftGenerationService()
    long_rule = "Use cautious wording. " * 40

    rules_text = service._format_learning_rules(
        [
            {
                "rule_type": "tone",
                "rule_description": long_rule,
                "example_before": "John failed to pay rent.",
                "example_after": "The document states John allegedly failed to pay rent.",
            },
            {
                "rule_type": "citation",
                "rule_description": "Prefer page-level citations after factual claims.",
            },
        ]
    )

    assert "Tone:" in rules_text
    assert "Citation:" in rules_text
    assert "..." in rules_text
    assert len(rules_text.splitlines()[1]) < 340

from dataclasses import dataclass

from app.core.config import settings
from app.models.schemas import EvidenceChunk
from app.services.llm_service import (
    GitHubModelsService,
    LlmResponseError,
    LlmTimeoutError,
    LlmUnavailableError,
)
from app.services.retrieval_service import RetrievalService


class NoEvidenceFoundError(Exception):
    pass


class UnsupportedDraftTypeError(Exception):
    pass


@dataclass(frozen=True)
class DraftGenerationResult:
    draft: str
    evidence: list[EvidenceChunk]
    model_used: str
    grounding_note: str


class DraftGenerationService:
    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        llm_service: GitHubModelsService | None = None,
    ) -> None:
        self.retrieval_service = retrieval_service or RetrievalService()
        self.llm_service = llm_service or GitHubModelsService()

    async def generate_case_fact_summary(
        self,
        *,
        document_id: int,
        draft_type: str,
        top_k: int,
        learning_rules: list[dict[str, object]],
    ) -> DraftGenerationResult:
        if draft_type != "case_fact_summary":
            raise UnsupportedDraftTypeError("Only case_fact_summary is supported.")

        retrieval_result = self.retrieval_service.query(
            document_id=document_id,
            query="Generate a case fact summary from this document.",
            top_k=top_k,
        )
        if not retrieval_result.evidence:
            raise NoEvidenceFoundError("No evidence found for draft generation.")

        system_prompt, user_prompt = self.build_case_fact_summary_prompt(
            evidence=retrieval_result.evidence,
            learning_rules=learning_rules,
        )
        draft = await self.llm_service.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return DraftGenerationResult(
            draft=draft,
            evidence=retrieval_result.evidence,
            model_used=settings.github_models_model,
            grounding_note="Draft generated only from retrieved evidence.",
        )

    def build_case_fact_summary_prompt(
        self,
        *,
        evidence: list[EvidenceChunk],
        learning_rules: list[dict[str, object]],
    ) -> tuple[str, str]:
        system_prompt = (
            "You are a careful legal drafting assistant. Generate cautious legal-style "
            "draft text only from the supplied evidence. Do not provide legal advice."
        )

        rules_text = self._format_learning_rules(learning_rules)
        evidence_text = self._format_evidence(evidence)
        user_prompt = f"""
Generate a first-pass case fact summary using only the evidence below.

Mandatory rules:
- Use only the provided evidence.
- Every factual claim must include a source reference like [E1 p.2].
- If information is missing, write "Not found in the provided documents."
- Do not invent facts.
- Do not provide legal advice.
- Use cautious legal-style wording.
- Include unclear OCR warnings where relevant.
- Follow any active learning rules unless they conflict with grounding.

Required draft structure:
# Case Fact Summary

## 1. Parties Involved
## 2. Key Dates
## 3. Important Facts
## 4. Source Evidence
## 5. Missing or Unclear Information
## 6. Suggested Next Review Points

Active learning rules:
{rules_text}

Retrieved evidence:
{evidence_text}
""".strip()
        return system_prompt, user_prompt

    def _format_learning_rules(self, learning_rules: list[dict[str, object]]) -> str:
        if not learning_rules:
            return "No active learning rules."
        lines = []
        for index, rule in enumerate(learning_rules, start=1):
            lines.append(
                f"{index}. {rule.get('rule_name')}: {rule.get('rule_description')}"
            )
        return "\n".join(lines)

    def _format_evidence(self, evidence: list[EvidenceChunk]) -> str:
        blocks = []
        for index, item in enumerate(evidence, start=1):
            confidence = item.source.ocr_confidence
            unclear_note = ""
            if confidence is not None and confidence < settings.ocr_confidence_threshold:
                unclear_note = " OCR warning: confidence is below the configured threshold."
            blocks.append(
                "\n".join(
                    [
                        f"[E{index} p.{item.page_number}]",
                        f"Filename: {item.source.filename}",
                        f"Source type: {item.source.source_type}",
                        f"OCR confidence: {confidence if confidence is not None else 'not applicable'}",
                        f"Relevance score: {item.relevance_score}",
                        f"Text: {item.text}",
                        unclear_note,
                    ]
                ).strip()
            )
        return "\n\n".join(blocks)


__all__ = [
    "DraftGenerationResult",
    "DraftGenerationService",
    "LlmResponseError",
    "LlmTimeoutError",
    "LlmUnavailableError",
    "NoEvidenceFoundError",
    "UnsupportedDraftTypeError",
]

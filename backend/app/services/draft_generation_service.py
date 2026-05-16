from dataclasses import dataclass

from app.core.config import settings
from app.models.schemas import EvidenceChunk, LearnedRule
from app.repositories.documents_repository import fetch_active_learning_rules
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
    applied_learning_rules: list[LearnedRule]
    learning_rules_warning: str | None = None


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

        learning_rules, learning_rules_warning = await self._load_active_learning_rules()
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
            applied_learning_rules=self._to_learned_rule_models(learning_rules),
            learning_rules_warning=learning_rules_warning,
        )

    async def _load_active_learning_rules(self) -> tuple[list[dict[str, object]], str | None]:
        try:
            return await fetch_active_learning_rules(limit=10), None
        except Exception:
            return (
                [],
                "Draft generated without learned rules because active rules could not be loaded.",
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
- Apply these operator-learned drafting preferences unless they conflict with grounding.

Required draft structure:
# Case Fact Summary

## 1. Parties Involved
## 2. Key Dates
## 3. Important Facts
## 4. Source Evidence
## 5. Missing or Unclear Information
## 6. Suggested Next Review Points

Apply these operator-learned drafting preferences:
{rules_text}

Retrieved evidence:
{evidence_text}
""".strip()
        return system_prompt, user_prompt

    def _format_learning_rules(self, learning_rules: list[dict[str, object]]) -> str:
        if not learning_rules:
            return "No active learning rules."
        grouped: dict[str, list[dict[str, object]]] = {}
        for rule in learning_rules:
            rule_type = str(rule.get("rule_type") or "drafting").strip() or "drafting"
            grouped.setdefault(rule_type, []).append(rule)

        lines = []
        index = 1
        for rule_type, rules in grouped.items():
            lines.append(f"{rule_type.title()}:")
            for rule in rules:
                rule_text = self._concise_rule_text(rule.get("rule_description"), limit=180)
                example_before = self._concise_rule_text(rule.get("example_before"), limit=160)
                example_after = self._concise_rule_text(rule.get("example_after"), limit=160)
                example_text = ""
                if example_before or example_after:
                    example_text = (
                        f" Example before: {example_before or 'n/a'}; "
                        f"example after: {example_after or 'n/a'}."
                    )
                lines.append(f"{index}. {rule_text}{example_text}")
                index += 1
        return "\n".join(lines)

    def _concise_rule_text(self, value: object, limit: int = 240) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."

    def _to_learned_rule_models(
        self,
        learning_rules: list[dict[str, object]],
    ) -> list[LearnedRule]:
        rules = []
        for index, rule in enumerate(learning_rules, start=1):
            rules.append(
                LearnedRule(
                    rule_id=str(rule.get("id") or index),
                    rule_type=str(rule.get("rule_type") or "drafting"),
                    rule_text=self._concise_rule_text(rule.get("rule_description")),
                    example_before=rule.get("example_before"),
                    example_after=rule.get("example_after"),
                    is_active=True,
                )
            )
        return rules

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

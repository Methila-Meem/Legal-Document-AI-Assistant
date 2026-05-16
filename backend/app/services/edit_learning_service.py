import difflib
import json
from dataclasses import dataclass
from json import JSONDecodeError

from pydantic import BaseModel, Field, ValidationError

from app.services.llm_service import (
    GitHubModelsService,
    LlmResponseError,
    LlmTimeoutError,
    LlmUnavailableError,
)


class LearnedRuleCandidate(BaseModel):
    rule_type: str = Field(default="drafting")
    rule_text: str
    example_before: str | None = None
    example_after: str | None = None


class LearnedRuleSet(BaseModel):
    rules: list[LearnedRuleCandidate] = []


class InvalidRuleJsonError(Exception):
    pass


@dataclass(frozen=True)
class RuleExtractionResult:
    diff_text: str
    rules: list[dict[str, object]]
    warning: str | None = None


class EditLearningService:
    def __init__(self, llm_service: GitHubModelsService | None = None) -> None:
        self.llm_service = llm_service or GitHubModelsService()

    async def extract_rules(
        self,
        *,
        original_draft: str,
        edited_draft: str,
    ) -> RuleExtractionResult:
        diff_text = self.build_diff(original_draft=original_draft, edited_draft=edited_draft)

        try:
            rules = await self._extract_rules_with_llm(
                original_draft=original_draft,
                edited_draft=edited_draft,
                diff_text=diff_text,
            )
            return RuleExtractionResult(diff_text=diff_text, rules=rules)
        except LlmUnavailableError:
            return RuleExtractionResult(
                diff_text=diff_text,
                rules=[],
                warning="Operator edit was saved, but rule extraction failed because the LLM is unavailable.",
            )
        except LlmTimeoutError:
            return RuleExtractionResult(
                diff_text=diff_text,
                rules=[],
                warning="Operator edit was saved, but rule extraction timed out.",
            )
        except (LlmResponseError, InvalidRuleJsonError):
            fallback_rules = self._build_heuristic_rules(
                original_draft=original_draft,
                edited_draft=edited_draft,
            )
            warning = (
                "Operator edit was saved, but LLM rule JSON was invalid. "
                "A heuristic learned rule was created."
                if fallback_rules
                else "Operator edit was saved, but rule extraction failed and no heuristic rule was found."
            )
            return RuleExtractionResult(
                diff_text=diff_text,
                rules=fallback_rules,
                warning=warning,
            )

    def build_diff(self, *, original_draft: str, edited_draft: str) -> str:
        original_lines = original_draft.splitlines()
        edited_lines = edited_draft.splitlines()
        diff = difflib.unified_diff(
            original_lines,
            edited_lines,
            fromfile="original_draft",
            tofile="edited_draft",
            lineterm="",
        )
        return "\n".join(diff)

    async def _extract_rules_with_llm(
        self,
        *,
        original_draft: str,
        edited_draft: str,
        diff_text: str,
    ) -> list[dict[str, object]]:
        system_prompt = (
            "You extract reusable legal drafting improvement rules from operator edits. "
            "Return only valid JSON. Do not return a side-by-side diff."
        )
        user_prompt = f"""
Compare the original generated draft, the operator edited draft, and the diff.

Extract reusable drafting rules that should improve future drafts. Rules must be general enough
to reuse on future legal-style drafts, while preserving evidence grounding and cautious wording.
Do not simply describe this one edit.

Return JSON exactly in this shape:
{{
  "rules": [
    {{
      "rule_type": "tone|structure|citation|clarity|drafting",
      "rule_text": "Reusable instruction for future drafts.",
      "example_before": "Short phrase from the original draft, if available.",
      "example_after": "Short phrase from the edited draft, if available."
    }}
  ]
}}

Original draft:
{original_draft[:12000]}

Edited draft:
{edited_draft[:12000]}

Diff:
{diff_text[:8000]}
""".strip()

        content = await self.llm_service.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
        )
        return self._parse_rule_json(content)

    def _parse_rule_json(self, content: str) -> list[dict[str, object]]:
        try:
            parsed = json.loads(content)
            rule_set = LearnedRuleSet.model_validate(parsed)
        except (JSONDecodeError, ValidationError) as exc:
            raise InvalidRuleJsonError("Rule extraction returned invalid JSON.") from exc

        rules: list[dict[str, object]] = []
        for rule in rule_set.rules:
            rule_text = rule.rule_text.strip()
            if not rule_text:
                continue
            rules.append(
                {
                    "rule_type": rule.rule_type.strip() or "drafting",
                    "rule_text": rule_text,
                    "example_before": rule.example_before,
                    "example_after": rule.example_after,
                }
            )
        if not rules:
            raise InvalidRuleJsonError("Rule extraction returned no usable rules.")
        return rules

    def _build_heuristic_rules(
        self,
        *,
        original_draft: str,
        edited_draft: str,
    ) -> list[dict[str, object]]:
        original_lower = original_draft.lower()
        edited_lower = edited_draft.lower()

        if (
            "the document states" in edited_lower
            and "the document states" not in original_lower
        ) or ("allegedly" in edited_lower and "allegedly" not in original_lower):
            before, after = self._first_changed_line_pair(original_draft, edited_draft)
            return [
                {
                    "rule_type": "tone",
                    "rule_text": (
                        "Use cautious legal wording such as 'the document states' or "
                        "'allegedly' instead of presenting claims as confirmed facts."
                    ),
                    "example_before": before,
                    "example_after": after,
                }
            ]

        before, after = self._first_changed_line_pair(original_draft, edited_draft)
        if before and after:
            return [
                {
                    "rule_type": "drafting",
                    "rule_text": (
                        "Prefer the operator's revised wording pattern when future drafts "
                        "contain similar phrasing, while keeping source citations intact."
                    ),
                    "example_before": before,
                    "example_after": after,
                }
            ]
        return []

    def _first_changed_line_pair(
        self,
        original_draft: str,
        edited_draft: str,
    ) -> tuple[str | None, str | None]:
        matcher = difflib.SequenceMatcher(
            None,
            original_draft.splitlines(),
            edited_draft.splitlines(),
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            before = " ".join(line.strip() for line in original_draft.splitlines()[i1:i2])
            after = " ".join(line.strip() for line in edited_draft.splitlines()[j1:j2])
            return before[:500] or None, after[:500] or None
        return None, None


__all__ = [
    "EditLearningService",
    "InvalidRuleJsonError",
    "RuleExtractionResult",
]

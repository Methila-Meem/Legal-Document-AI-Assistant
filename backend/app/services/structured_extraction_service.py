import re
from dataclasses import dataclass

from app.models.schemas import KeyEvent, StructuredFields
from app.services.llm_service import GitHubModelsService, LlmResponseError, LlmUnavailableError


@dataclass(frozen=True)
class StructuredExtractionResult:
    fields: StructuredFields
    method: str
    warnings: list[str]


class StructuredExtractionService:
    date_patterns = [
        re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
        re.compile(
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
            r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    ]
    money_pattern = re.compile(r"(?<!\w)(?:USD\s*)?\$\s?\d[\d,]*(?:\.\d{2})?|\b\d[\d,]*(?:\.\d{2})?\s+dollars\b", re.IGNORECASE)
    case_pattern = re.compile(
        r"\b(?:case|docket|matter|file)\s*(?:no\.?|number|#)?\s*[:#-]?\s*([A-Z0-9][A-Z0-9\-:/]{3,})",
        re.IGNORECASE,
    )
    address_pattern = re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9.\s]+(?:Street|St\.|Avenue|Ave\.|Road|Rd\.|"
        r"Boulevard|Blvd\.|Drive|Dr\.|Lane|Ln\.|Court|Ct\.)\b(?:,\s*[A-Za-z.\s]+)?",
        re.IGNORECASE,
    )
    party_pattern = re.compile(
        r"\b(?:between|by and between|from|to|plaintiff|defendant|landlord|tenant|"
        r"buyer|seller|party)\s*:?\s+([A-Z][A-Za-z0-9&.,' -]{2,80})",
        re.IGNORECASE,
    )

    def __init__(self, llm_service: GitHubModelsService | None = None) -> None:
        self.llm_service = llm_service or GitHubModelsService()

    async def extract(self, pages: list[dict[str, object]]) -> StructuredExtractionResult:
        rules_fields = self._extract_with_rules(pages)
        warnings: list[str] = []

        if not self.llm_service.is_available:
            warnings.append("GitHub Models API key is not configured; used rule-based extraction only.")
            return StructuredExtractionResult(fields=rules_fields, method="rules", warnings=warnings)

        document_text = self._format_pages_for_llm(pages)
        try:
            llm_fields = await self.llm_service.extract_structured_fields(document_text)
        except LlmUnavailableError:
            warnings.append("GitHub Models API key is not configured; used rule-based extraction only.")
            return StructuredExtractionResult(fields=rules_fields, method="rules", warnings=warnings)
        except LlmResponseError:
            warnings.append("LLM extraction failed or returned invalid JSON; used rule-based extraction only.")
            return StructuredExtractionResult(fields=rules_fields, method="rules", warnings=warnings)

        merged = self._merge_fields(rules_fields, llm_fields)
        return StructuredExtractionResult(fields=merged, method="hybrid", warnings=warnings)

    def _extract_with_rules(self, pages: list[dict[str, object]]) -> StructuredFields:
        all_text = "\n".join(str(page["text"]) for page in pages)
        dates = self._unique(match.group(0) for pattern in self.date_patterns for match in pattern.finditer(all_text))
        monetary_amounts = self._unique(match.group(0) for match in self.money_pattern.finditer(all_text))
        case_numbers = self._unique(match.group(1) for match in self.case_pattern.finditer(all_text))
        addresses = self._unique(match.group(0) for match in self.address_pattern.finditer(all_text))
        parties = self._extract_parties(all_text)

        document_type = self._detect_document_type(all_text)
        key_events = [
            KeyEvent(event="Date referenced", date=date, source_page=self._find_source_page(date, pages))
            for date in dates[:5]
        ]
        unclear_items = [
            f"Page {page['page_number']} may contain unclear OCR text."
            for page in pages
            if page.get("is_unclear")
        ]

        return StructuredFields(
            document_type=document_type,
            parties=parties,
            dates=dates,
            addresses=addresses,
            monetary_amounts=monetary_amounts,
            case_numbers=case_numbers,
            key_events=key_events,
            unclear_items=unclear_items,
        )

    def _detect_document_type(self, text: str) -> str | None:
        lowered = text.lower()
        candidates = [
            ("Notice", ["notice", "demand letter"]),
            ("Agreement", ["agreement", "contract"]),
            ("Lease", ["lease"]),
            ("Complaint", ["complaint", "plaintiff", "defendant"]),
            ("Invoice", ["invoice", "amount due"]),
            ("Court Order", ["order", "ordered by the court"]),
        ]
        for label, terms in candidates:
            if any(term in lowered for term in terms):
                return label
        return None

    def _merge_fields(self, rules_fields: StructuredFields, llm_fields: StructuredFields) -> StructuredFields:
        return StructuredFields(
            document_type=llm_fields.document_type or rules_fields.document_type,
            parties=self._unique([*rules_fields.parties, *llm_fields.parties]),
            dates=self._unique([*rules_fields.dates, *llm_fields.dates]),
            addresses=self._unique([*rules_fields.addresses, *llm_fields.addresses]),
            monetary_amounts=self._unique([*rules_fields.monetary_amounts, *llm_fields.monetary_amounts]),
            case_numbers=self._unique([*rules_fields.case_numbers, *llm_fields.case_numbers]),
            key_events=[*rules_fields.key_events, *llm_fields.key_events],
            unclear_items=self._unique([*rules_fields.unclear_items, *llm_fields.unclear_items]),
        )

    def _format_pages_for_llm(self, pages: list[dict[str, object]]) -> str:
        return "\n\n".join(
            f"Page {page['page_number']}:\n{page['text']}"
            for page in pages
            if str(page.get("text", "")).strip()
        )

    def _find_source_page(self, value: str, pages: list[dict[str, object]]) -> int | None:
        for page in pages:
            if value in str(page["text"]):
                return int(page["page_number"])
        return None

    def _clean_party(self, value: str) -> str:
        cleaned = value.strip(" .,\n\t")
        stop_markers = [
            ". Amount",
            ". Date",
            ". Case",
            ". Notice",
            ". Mail",
            " Amount due",
            " Case No",
            " Mail to",
        ]
        for marker in stop_markers:
            if marker.lower() in cleaned.lower():
                index = cleaned.lower().find(marker.lower())
                cleaned = cleaned[:index]
        return cleaned.strip(" .,\n\t")

    def _extract_parties(self, text: str) -> list[str]:
        candidates: list[str] = []
        for match in self.party_pattern.finditer(text):
            cleaned = self._clean_party(match.group(1))
            parts = re.split(r"\s+(?:and|&)\s+", cleaned)
            candidates.extend(part.strip(" .,\n\t") for part in parts)
        return self._unique(candidates)

    def _unique(self, values) -> list:
        seen = set()
        result = []
        for value in values:
            if value is None:
                continue
            cleaned = str(value).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                result.append(cleaned)
        return result

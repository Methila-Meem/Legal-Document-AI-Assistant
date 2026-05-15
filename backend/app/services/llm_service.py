import asyncio
import json

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import StructuredFields


class LlmUnavailableError(Exception):
    pass


class LlmResponseError(Exception):
    pass


class GitHubModelsService:
    def __init__(self) -> None:
        self.api_key = settings.github_models_api_key
        self.endpoint = settings.github_models_endpoint
        self.model = settings.github_models_model
        self.timeout = settings.llm_timeout_seconds
        self.max_retries = settings.llm_max_retries

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def extract_structured_fields(self, document_text: str) -> StructuredFields:
        if not self.is_available:
            raise LlmUnavailableError("GitHub Models API key is not configured.")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract structured fields from legal-style document text. "
                        "Return only valid JSON matching this schema: "
                        "{document_type:string|null, parties:string[], dates:string[], "
                        "addresses:string[], monetary_amounts:string[], case_numbers:string[], "
                        "key_events:[{event:string,date:string|null,source_page:number|null}], "
                        "unclear_items:string[]}."
                    ),
                },
                {
                    "role": "user",
                    "content": document_text[:24000],
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(self.endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return self._parse_structured_fields(content)
            except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise LlmResponseError("GitHub Models field extraction failed.") from last_error

    def _parse_structured_fields(self, content: str) -> StructuredFields:
        parsed = json.loads(content)
        return StructuredFields.model_validate(parsed)

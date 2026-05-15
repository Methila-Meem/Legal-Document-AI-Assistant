from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    page_number: int
    source_type: str | None
    ocr_confidence: float | None


class ChunkingService:
    def __init__(self) -> None:
        self.target_chars = settings.chunk_target_chars
        self.overlap_chars = settings.chunk_overlap_chars

    def create_chunks(self, pages: list[dict[str, object]]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        chunk_index = 0

        for page in pages:
            text = self._normalize_text(str(page.get("text") or ""))
            if not text:
                continue

            for content in self._split_text(text):
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        content=content,
                        page_number=int(page["page_number"]),
                        source_type=(
                            str(page["source_type"])
                            if page.get("source_type") is not None
                            else None
                        ),
                        ocr_confidence=(
                            float(page["ocr_confidence"])
                            if page.get("ocr_confidence") is not None
                            else None
                        ),
                    )
                )
                chunk_index += 1

        return chunks

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.target_chars:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.target_chars, len(text))
            if end < len(text):
                boundary = max(
                    text.rfind("\n", start, end),
                    text.rfind(". ", start, end),
                    text.rfind(" ", start, end),
                )
                min_boundary = start + max(200, self.target_chars // 2)
                if boundary >= min_boundary:
                    end = boundary + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break
            start = max(end - self.overlap_chars, start + 1)

        return chunks

    def _normalize_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

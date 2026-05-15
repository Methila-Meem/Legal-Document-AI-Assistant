from dataclasses import dataclass

from app.models.schemas import EvidenceChunk, EvidenceSource
from app.services.embedding_service import EmbeddingModelUnavailableError, EmbeddingService
from app.services.vector_store_service import VectorStoreError, VectorStoreService


@dataclass(frozen=True)
class RetrievalResult:
    query: str
    document_id: str
    evidence: list[EvidenceChunk]
    message: str | None = None


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store_service: VectorStoreService | None = None,
    ) -> None:
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store_service = vector_store_service or VectorStoreService()

    def query(self, *, document_id: int, query: str, top_k: int) -> RetrievalResult:
        embeddings = self.embedding_service.embed_texts([query])
        rows = self.vector_store_service.query_document_chunks(
            document_id=document_id,
            query_embedding=embeddings[0],
            top_k=top_k,
        )

        evidence = [self._to_evidence_chunk(row) for row in rows]
        return RetrievalResult(
            query=query,
            document_id=str(document_id),
            evidence=evidence,
            message=None if evidence else "No evidence found for this document and query.",
        )

    def _to_evidence_chunk(self, row: dict[str, object]) -> EvidenceChunk:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        metadata = metadata or {}
        return EvidenceChunk(
            chunk_id=str(metadata.get("chunk_id", "")),
            document_id=str(metadata.get("document_id", "")),
            page_number=int(metadata.get("page_number") or 0),
            text=str(row.get("text") or ""),
            relevance_score=float(row.get("relevance_score") or 0.0),
            source=EvidenceSource(
                filename=str(metadata.get("original_filename") or ""),
                source_type=str(metadata.get("source_type") or ""),
                ocr_confidence=(
                    float(metadata["ocr_confidence"])
                    if metadata.get("ocr_confidence") is not None
                    else None
                ),
            ),
        )


__all__ = [
    "EmbeddingModelUnavailableError",
    "RetrievalResult",
    "RetrievalService",
    "VectorStoreError",
]

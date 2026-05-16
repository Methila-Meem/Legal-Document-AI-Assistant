from dataclasses import dataclass
from uuid import uuid4

from app.core.config import settings
from app.repositories.documents_repository import (
    DocumentRecord,
    delete_document_chunks,
    fetch_processed_pages,
    insert_chunks,
    update_document_status,
)
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingModelUnavailableError, EmbeddingService
from app.services.vector_store_service import VectorStoreError, VectorStoreService


class EmptyExtractedTextError(Exception):
    pass


@dataclass(frozen=True)
class IndexingResult:
    document_id: str
    status: str
    chunk_count: int
    embedding_model: str
    vector_db: str


class IndexingService:
    def __init__(
        self,
        chunking_service: ChunkingService | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store_service: VectorStoreService | None = None,
    ) -> None:
        self.chunking_service = chunking_service or ChunkingService()
        self.embedding_service = embedding_service or EmbeddingService()
        self.vector_store_service = vector_store_service or VectorStoreService()

    async def index_document(self, document: DocumentRecord) -> IndexingResult:
        pages = await fetch_processed_pages(document.id)
        chunks = self.chunking_service.create_chunks(pages)
        if not chunks:
            raise EmptyExtractedTextError("No extracted text is available for indexing.")

        await delete_document_chunks(document.id)

        chunk_records = [
            {
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding_id": f"doc-{document.id}-chunk-{chunk.chunk_index}-{uuid4().hex}",
                "metadata": {
                    "document_id": str(document.id),
                    "page_number": chunk.page_number,
                    "original_filename": document.original_filename,
                    "source_type": chunk.source_type or "",
                    "ocr_confidence": chunk.ocr_confidence,
                    "ocr_engine": chunk.ocr_engine or "",
                },
            }
            for chunk in chunks
        ]
        inserted_chunks = await insert_chunks(document.id, chunk_records)

        embeddings = self.embedding_service.embed_texts(
            [str(chunk["content"]) for chunk in inserted_chunks]
        )
        self.vector_store_service.replace_document_chunks(
            document_id=document.id,
            chunks=inserted_chunks,
            embeddings=embeddings,
        )
        await update_document_status(document.id, "indexed")

        return IndexingResult(
            document_id=str(document.id),
            status="indexed",
            chunk_count=len(inserted_chunks),
            embedding_model=settings.embedding_model_name,
            vector_db="ChromaDB",
        )


__all__ = [
    "EmbeddingModelUnavailableError",
    "EmptyExtractedTextError",
    "IndexingResult",
    "IndexingService",
    "VectorStoreError",
]

from pathlib import Path

from app.core.config import settings


class VectorStoreError(Exception):
    pass


class VectorStoreService:
    def __init__(self) -> None:
        self.persist_directory = Path(settings.storage_dir) / "chroma"
        self.collection_name = settings.chroma_collection_name

    def replace_document_chunks(
        self,
        *,
        document_id: int,
        chunks: list[dict[str, object]],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("Chunk and embedding counts do not match.")

        try:
            collection = self._get_collection()
            collection.delete(where={"document_id": str(document_id)})
            if not chunks:
                return

            collection.add(
                ids=[str(chunk["embedding_id"]) for chunk in chunks],
                documents=[str(chunk["content"]) for chunk in chunks],
                embeddings=embeddings,
                metadatas=[self._metadata(chunk) for chunk in chunks],
            )
        except Exception as exc:
            raise VectorStoreError("Unable to write chunks to ChromaDB.") from exc

    def _get_collection(self):
        import chromadb

        self.persist_directory.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.persist_directory))
        return client.get_or_create_collection(name=self.collection_name)

    def _metadata(self, chunk: dict[str, object]) -> dict[str, object]:
        metadata = dict(chunk["metadata"])
        metadata["chunk_id"] = int(chunk["chunk_id"])
        metadata["document_id"] = str(metadata["document_id"])
        if metadata.get("ocr_confidence") is None:
            metadata.pop("ocr_confidence", None)
        return metadata

import os
from threading import Lock

from app.core.config import settings


class EmbeddingModelUnavailableError(Exception):
    pass


class EmbeddingService:
    _model: object | None = None
    _model_name: str | None = None
    _lock = Lock()

    def __init__(self) -> None:
        self.model_name = settings.embedding_model_name

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        model = self._get_model()
        try:
            embeddings = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        except Exception as exc:
            raise EmbeddingModelUnavailableError("Embedding generation failed.") from exc

        return embeddings.astype(float).tolist()

    def _get_model(self) -> object:
        with self._lock:
            if self.__class__._model is not None and self.__class__._model_name == self.model_name:
                return self.__class__._model

            try:
                self._configure_cache_environment()
                from sentence_transformers import SentenceTransformer

                self.__class__._model = SentenceTransformer(self.model_name)
                self.__class__._model_name = self.model_name
            except Exception as exc:
                raise EmbeddingModelUnavailableError(
                    "Embedding model could not be loaded."
                ) from exc

            return self.__class__._model

    def _configure_cache_environment(self) -> None:
        cache_dir = settings.storage_dir / "processed" / "embedding_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(cache_dir))
        os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))

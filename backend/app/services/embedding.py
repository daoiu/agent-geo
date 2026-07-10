"""Embedding service wrapping bge-small-zh-v1.5 via sentence-transformers."""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIM = 512


class EmbeddingService:
    """Lazy-loaded, cached embedding model wrapper.

    Model is loaded on first call to embed() and cached as a class-level
    singleton. Subsequent calls reuse the same instance.
    """

    _model: SentenceTransformer | None = None

    @classmethod
    def _get_model(cls) -> SentenceTransformer:
        if cls._model is None:
            settings = get_settings()
            cls._model = SentenceTransformer(
                EMBEDDING_MODEL_NAME,
                cache_folder=settings.models_cache_dir,
            )
        return cls._model

    @classmethod
    def embed(cls, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns a list of 512-dim vectors (normalized)."""
        if not texts:
            return []
        model = cls._get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        # numpy array → list of lists
        return embeddings.tolist()
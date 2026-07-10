"""Tests for EmbeddingService."""
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from app.services.embedding import EmbeddingService


class TestEmbed:
    def test_embed_returns_list_of_vectors(self) -> None:
        """embed() should return a list with one 512-dim vector per input text."""
        # Mock sentence-transformers so we don't actually load the model
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            # Return 2 vectors of dim 512 (the bge-small-zh-v1.5 output dim)
            mock_model.encode.return_value = np.random.rand(2, 512).astype(np.float32)
            MockST.return_value = mock_model

            # Reset class-level cache
            EmbeddingService._model = None

            vectors = EmbeddingService.embed(["hello", "world"])

            assert len(vectors) == 2
            assert len(vectors[0]) == 512
            assert len(vectors[1]) == 512

    def test_embed_normalizes(self) -> None:
        """embed() should call encode with normalize_embeddings=True."""
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.1] * 512], dtype=np.float32)
            MockST.return_value = mock_model
            EmbeddingService._model = None

            EmbeddingService.embed(["test"])
            # Check that normalize_embeddings was passed
            call_kwargs = mock_model.encode.call_args.kwargs
            assert call_kwargs.get("normalize_embeddings") is True

    def test_model_is_cached(self) -> None:
        """Second call should not re-instantiate SentenceTransformer."""
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.1] * 512], dtype=np.float32)
            MockST.return_value = mock_model
            EmbeddingService._model = None

            EmbeddingService.embed(["x"])
            EmbeddingService.embed(["y"])
            # Should be called only once
            assert MockST.call_count == 1

    def test_model_path_uses_configured_dir(self) -> None:
        """SentenceTransformer should be initialized with the configured cache_folder."""
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.1] * 512], dtype=np.float32)
            MockST.return_value = mock_model
            EmbeddingService._model = None

            with patch("app.services.embedding.get_settings") as mock_get_settings:
                mock_get_settings.return_value = MagicMock(models_cache_dir="/custom/path/")
                EmbeddingService.embed(["test"])
                call_kwargs = MockST.call_args.kwargs
                assert call_kwargs.get("cache_folder") == "/custom/path/"
"""EmbeddingService 测试(bge-small-zh-v1.5 包装)。"""
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from app.services.embedding import EmbeddingService


class TestEmbed:
    def test_embed_returns_list_of_vectors(self) -> None:
        """embed() 应返回与输入文本数对应的 512 维向量列表。"""
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            # 返回 2 个 512 维向量(模拟 bge-small-zh-v1.5 输出)
            mock_model.encode.return_value = np.random.rand(2, 512).astype(np.float32)
            MockST.return_value = mock_model

            # 重置 class-level 缓存
            EmbeddingService._model = None

            vectors = EmbeddingService.embed(["hello", "world"])

            assert len(vectors) == 2
            assert len(vectors[0]) == 512
            assert len(vectors[1]) == 512

    def test_embed_normalizes(self) -> None:
        """embed() 应传 normalize_embeddings=True(余弦距离要求向量归一化)。"""
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.1] * 512], dtype=np.float32)
            MockST.return_value = mock_model
            EmbeddingService._model = None

            EmbeddingService.embed(["test"])
            call_kwargs = mock_model.encode.call_args.kwargs
            assert call_kwargs.get("normalize_embeddings") is True

    def test_model_is_cached(self) -> None:
        """第二次调用不应重新实例化 SentenceTransformer(避免 5-10s 模型加载)。"""
        with patch("app.services.embedding.SentenceTransformer") as MockST:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.array([[0.1] * 512], dtype=np.float32)
            MockST.return_value = mock_model
            EmbeddingService._model = None

            EmbeddingService.embed(["x"])
            EmbeddingService.embed(["y"])
            # 应只调用一次
            assert MockST.call_count == 1

    def test_model_path_uses_configured_dir(self) -> None:
        """SentenceTransformer 应使用配置中的 cache_folder 路径(让 Docker COPY 生效)。"""
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
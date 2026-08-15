"""VectorIndex (ChromaDB 封装) 测试。"""
from unittest.mock import patch, MagicMock

import pytest

from app.domain.knowledge.vector_index import VectorIndex


@pytest.fixture
def mock_chroma():
    """Mock ChromaDB PersistentClient,提供 mock collection。每个测试重置单例。"""
    from app.domain.knowledge.vector_index import VectorIndex
    VectorIndex._client = None
    with patch("app.domain.knowledge.vector_index.chromadb") as MockChroma:
        mock_client = MagicMock()
        MockChroma.PersistentClient.return_value = mock_client
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        yield MockChroma, mock_client, mock_collection
    VectorIndex._client = None


class TestInit:
    def test_creates_collection_named_after_kb(self, mock_chroma) -> None:
        """构造时应创建名为 kb_<kb_id> 的 collection。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        VectorIndex("kb_123")
        mock_client.get_or_create_collection.assert_called_once()
        call_kwargs = mock_client.get_or_create_collection.call_args.kwargs
        assert call_kwargs["name"] == "kb_kb_123"


class TestAddChunks:
    def test_add_chunks_calls_collection_add(self, mock_chroma) -> None:
        """add_chunks 应调 collection.add 并传入预计算的 embeddings。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.add_chunks(
            [
                {"id": "c1", "content": "text 1", "doc_id": "d1", "chunk_index": 0},
                {"id": "c2", "content": "text 2", "doc_id": "d1", "chunk_index": 1},
            ],
            embeddings=[[0.1] * 512, [0.2] * 512],
        )
        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["ids"] == ["c1", "c2"]
        assert call_kwargs["documents"] == ["text 1", "text 2"]
        assert call_kwargs["embeddings"] == [[0.1] * 512, [0.2] * 512]

    def test_add_chunks_skips_empty_list(self, mock_chroma) -> None:
        """空列表应直接返回,不调 collection.add。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.add_chunks([], embeddings=[])
        mock_collection.add.assert_not_called()

    def test_add_chunks_requires_embeddings(self, mock_chroma) -> None:
        """不传 embeddings 应抛 ValueError(防止 ChromaDB 用默认 embedding 错模型)。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        with pytest.raises(ValueError, match="必须由调用方预计算"):
            index.add_chunks([{"id": "c1", "content": "x", "doc_id": "d1", "chunk_index": 0}])

    def test_add_chunks_validates_embeddings_length(self, mock_chroma) -> None:
        """embeddings 数量与 chunks 不匹配应抛 ValueError。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        with pytest.raises(ValueError, match="不匹配"):
            index.add_chunks(
                [
                    {"id": "c1", "content": "x", "doc_id": "d1", "chunk_index": 0},
                    {"id": "c2", "content": "y", "doc_id": "d1", "chunk_index": 1},
                ],
                embeddings=[[0.1] * 512],  # 1 个向量对应 2 个 chunks
            )


class TestQuery:
    def test_query_returns_flattened_results(self, mock_chroma) -> None:
        """query 应展开 ChromaDB 嵌套列表,返回统一 dict 列表。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        mock_collection.query.return_value = {
            "ids": [["c1", "c2"]],
            "documents": [["text 1", "text 2"]],
            "metadatas": [[{"doc_id": "d1"}, {"doc_id": "d1"}]],
            "distances": [[0.1, 0.2]],
        }
        index = VectorIndex("kb1")
        results = index.query("test query", top_k=5)
        assert len(results) == 2
        assert results[0]["id"] == "c1"
        assert results[0]["content"] == "text 1"
        assert results[0]["distance"] == 0.1
        assert results[1]["distance"] == 0.2

    def test_query_returns_empty_list_on_no_results(self, mock_chroma) -> None:
        """无结果时应返回空列表(不抛错)。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        index = VectorIndex("kb1")
        results = index.query("test", top_k=5)
        assert results == []


class TestDelete:
    def test_delete_chunks(self, mock_chroma) -> None:
        """delete_chunks 应调 collection.delete。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.delete_chunks(["c1", "c2"])
        mock_collection.delete.assert_called_once_with(ids=["c1", "c2"])

    def test_delete_chunks_skips_empty_list(self, mock_chroma) -> None:
        """空列表应直接返回。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.delete_chunks([])
        mock_collection.delete.assert_not_called()


class TestGetAllIds:
    def test_returns_set_of_ids(self, mock_chroma) -> None:
        """get_all_ids 应返回所有已索引 chunk id 的 set。"""
        MockChroma, mock_client, mock_collection = mock_chroma
        mock_collection.get.return_value = {"ids": ["c1", "c2", "c3"]}
        index = VectorIndex("kb1")
        all_ids = index.get_all_ids()
        assert all_ids == {"c1", "c2", "c3"}
        assert isinstance(all_ids, set)
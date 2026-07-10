"""Tests for VectorIndex (ChromaDB wrapper)."""
from unittest.mock import patch, MagicMock

import pytest

from app.domain.knowledge.vector_index import VectorIndex


@pytest.fixture
def mock_chroma():
    """Patch the ChromaDB PersistentClient and provide a mock collection."""
    # Reset class-level singleton so each test gets fresh state
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
        MockChroma, mock_client, mock_collection = mock_chroma
        VectorIndex("kb_123")
        mock_client.get_or_create_collection.assert_called_once()
        call_kwargs = mock_client.get_or_create_collection.call_args.kwargs
        assert call_kwargs["name"] == "kb_kb_123"


class TestAddChunks:
    def test_add_chunks_calls_collection_add(self, mock_chroma) -> None:
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.add_chunks([
            {"id": "c1", "content": "text 1", "doc_id": "d1", "chunk_index": 0},
            {"id": "c2", "content": "text 2", "doc_id": "d1", "chunk_index": 1},
        ])
        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args.kwargs
        assert call_kwargs["ids"] == ["c1", "c2"]
        assert call_kwargs["documents"] == ["text 1", "text 2"]

    def test_add_chunks_skips_empty_list(self, mock_chroma) -> None:
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.add_chunks([])
        mock_collection.add.assert_not_called()


class TestQuery:
    def test_query_returns_flattened_results(self, mock_chroma) -> None:
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
        MockChroma, mock_client, mock_collection = mock_chroma
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        index = VectorIndex("kb1")
        results = index.query("test", top_k=5)
        assert results == []


class TestDelete:
    def test_delete_chunks(self, mock_chroma) -> None:
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.delete_chunks(["c1", "c2"])
        mock_collection.delete.assert_called_once_with(ids=["c1", "c2"])

    def test_delete_chunks_skips_empty_list(self, mock_chroma) -> None:
        MockChroma, mock_client, mock_collection = mock_chroma
        index = VectorIndex("kb1")
        index.delete_chunks([])
        mock_collection.delete.assert_not_called()


class TestGetAllIds:
    def test_returns_set_of_ids(self, mock_chroma) -> None:
        MockChroma, mock_client, mock_collection = mock_chroma
        mock_collection.get.return_value = {"ids": ["c1", "c2", "c3"]}
        index = VectorIndex("kb1")
        all_ids = index.get_all_ids()
        assert all_ids == {"c1", "c2", "c3"}
        assert isinstance(all_ids, set)
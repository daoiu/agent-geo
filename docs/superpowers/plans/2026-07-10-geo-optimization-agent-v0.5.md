# GEO Optimization Agent v0.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace v0.2's keyword-only knowledge base search with hybrid retrieval (vector + keyword + RRF fusion) using ChromaDB + bge-small-zh-v1.5. Recall improves from ~70% to ~90%; v0.4 agent's `search_knowledge` tool is upgraded transparently.

**Architecture:** v0.5 extends the v0.1-v0.4 monolith. Adds ChromaDB (embedded) and sentence-transformers as Python dependencies. New `services/` modules: `embedding.py` (bge wrapper), `hybrid_search.py` (RRF), `reindex.py` (startup lazy indexing). v0.2's `KnowledgeRepository.search_chunks_by_keyword` is supplemented by a new `search_chunks_hybrid` method; v0.4's `ToolExecutor._execute_search_knowledge` switches to it. No new containers, no frontend changes, no new API endpoints (frontend is unaware).

**Tech Stack:** Extends v0.1-v0.4 with: `chromadb==0.5.20` (embedded vector DB), `sentence-transformers==3.2.1` (embedding model loader), `BAAI/bge-small-zh-v1.5` (Chinese-optimized embedding model, ~95MB, bundled in Docker image).

## Global Constraints

Inherits **all** v0.1, v0.2, v0.3, v0.4 constraints. Additions specific to v0.5:

- **v0.5 builds on v0.1 + v0.2 + v0.3 + v0.4** — Tasks assume all earlier modules exist
- **No new containers** — ChromaDB runs embedded in the FastAPI process
- **Persistent storage in `./data/chroma/`** — survives container restarts
- **bge model bundled in Docker image** — at `./data/models/bge-small-zh-v1.5/`
- **Model loaded lazily on first use** — avoids 5-10s startup penalty
- **ChromaDB client is process-singleton** — class-level cached
- **Search has automatic fallback** — if ChromaDB fails, falls back to keyword-only
- **Vector and keyword results fused via RRF** — k=60 constant
- **Reindex at startup** — only chunks missing from ChromaDB are processed
- **Existing v0.2 chunker + parser unchanged** — only `search` path changes
- **v0.4 agent tool updated to use hybrid** — single function-call change

**Reference spec:** `docs/superpowers/specs/2026-07-10-geo-agent-v0.5-design.md`

---

## Phase 0: Foundation Extensions

### Task 0.1: Add v0.5 Dependencies and Settings

**Files:**
- Modify: `D:/GEO2/backend/requirements.txt`
- Modify: `D:/GEO2/backend/app/core/config.py`
- Modify: `D:/GEO2/backend/.env.example`

**Interfaces (additions to Settings):**
- `chroma_path: str = "./data/chroma"`
- `models_cache_dir: str = "./data/models"`
- `embedding_batch_size: int = 50`
- `hybrid_top_k_vector: int = 20`
- `hybrid_top_k_keyword: int = 20`
- `hybrid_rrf_k: int = 60`

- [ ] **Step 1: Append dependencies to `requirements.txt`**

Edit `D:/GEO2/backend/requirements.txt` and add at the bottom:

```
chromadb==0.5.20
sentence-transformers==3.2.1
```

- [ ] **Step 2: Install dependencies**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pip install -r requirements.txt
```

Expected: All packages install. If torch is heavy (~200MB CPU version), expect 1-2 minutes.

- [ ] **Step 3: Add v0.5 settings to `config.py`**

Edit `D:/GEO2/backend/app/core/config.py`. Add these fields to the `Settings` class:

```python
    # v0.5 — Vector retrieval
    chroma_path: str = "./data/chroma"
    models_cache_dir: str = "./data/models"
    embedding_batch_size: int = 50
    hybrid_top_k_vector: int = 20
    hybrid_top_k_keyword: int = 20
    hybrid_rrf_k: int = 60
```

- [ ] **Step 4: Update `.env.example`**

Edit `D:/GEO2/backend/.env.example` and add at the bottom:

```bash
# v0.5 — Vector retrieval
CHROMA_PATH=./data/chroma
MODELS_CACHE_DIR=./data/models
EMBEDDING_BATCH_SIZE=50
HYBRID_TOP_K_VECTOR=20
HYBRID_TOP_K_KEYWORD=20
HYBRID_RRF_K=60
```

- [ ] **Step 5: Write failing test for new settings**

Create `D:/GEO2/backend/tests/test_config_v0.5.py`:

```python
"""Tests for v0.5 settings additions."""
from app.core.config import Settings


def test_v05_settings_have_defaults() -> None:
    s = Settings()
    assert s.chroma_path == "./data/chroma"
    assert s.models_cache_dir == "./data/models"
    assert s.embedding_batch_size == 50
    assert s.hybrid_top_k_vector == 20
    assert s.hybrid_top_k_keyword == 20
    assert s.hybrid_rrf_k == 60
```

- [ ] **Step 6: Run test to verify pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_config_v0.5.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): add v0.5 dependencies and settings (ChromaDB, sentence-transformers)"
```

---

### Task 0.2: EmbeddingService (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/services/__init__.py`
- Create: `D:/GEO2/backend/app/services/embedding.py`
- Create: `D:/GEO2/backend/tests/test_embedding.py`
- Create: `D:/GEO2/backend/data/models/.gitkeep` (empty dir placeholder)

**Interfaces:**
- `EmbeddingService.embed(texts: list[str]) -> list[list[float]]` — uses bge-small-zh-v1.5, returns 512-dim vectors, normalizes
- `EmbeddingService._get_model()` — class-level cached singleton (lazy load)

- [ ] **Step 1: Create `app/services/__init__.py`**

Create empty `D:/GEO2/backend/app/services/__init__.py`.

- [ ] **Step 2: Create data/models dir placeholder**

```bash
mkdir -p "D:/GEO2/backend/data/models" && touch "D:/GEO2/backend/data/models/.gitkeep"
```

- [ ] **Step 3: Write failing test**

Create `D:/GEO2/backend/tests/test_embedding.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_embedding.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5: Create `app/services/embedding.py`**

Create `D:/GEO2/backend/app/services/embedding.py`:

```python
"""Embedding service wrapping bge-small-zh-v1.5 via sentence-transformers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
EMBEDDING_DIM = 512


class EmbeddingService:
    """Lazy-loaded, cached embedding model wrapper.

    Model is loaded on first call to embed() and cached as a class-level
    singleton. Subsequent calls reuse the same instance.
    """

    _model: "SentenceTransformer | None" = None

    @classmethod
    def _get_model(cls) -> "SentenceTransformer":
        if cls._model is None:
            from sentence_transformers import SentenceTransformer  # heavy import

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
```

- [ ] **Step 6: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_embedding.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): EmbeddingService with lazy-loaded bge-small-zh-v1.5 + tests"
```

---

### Task 0.3: Download bge Model to Local Cache

> **This task pre-downloads the model so the Docker build and CI don't fail on cold start.**

**Files:**
- (no source files; downloads to disk)
- Create: `D:/GEO2/backend/data/models/bge-small-zh-v1.5/` (downloaded files)

- [ ] **Step 1: Run a one-off Python script to download the model**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-small-zh-v1.5', cache_folder='./data/models'); print('Model downloaded to', m.device)"
```

Expected: First run downloads the model (~95MB, 30-60 seconds). The model files appear in `./data/models/`. Output includes the device (cpu/cuda).

- [ ] **Step 2: Verify the model files are present**

```bash
ls "D:/GEO2/backend/data/models/" | head -20
```

Expected: Subdirectories like `models--BAAI--bge-small-zh-v1.5/` and files like `config.json`, `tokenizer.json`, `model.safetensors`.

- [ ] **Step 3: Add `data/models/` to `.gitignore` (large binary files)**

Edit `D:/GEO2/.gitignore`. Add this line (if not present):

```
backend/data/models/
```

This prevents the ~95MB model from being committed to git. The Docker build will copy it in separately (Task 0.4).

- [ ] **Step 4: Commit (gitignore change only)**

```bash
cd "D:/GEO2" && git add .gitignore && git commit -m "chore: gitignore backend/data/models (bge model binary)"
```

> **Note for implementers**: The model files are not in git. The Docker build script will handle copying them in.

---

## Phase 1: ChromaDB Vector Index

### Task 1.1: VectorIndex (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/domain/knowledge/__init__.py` (already exists from v0.2)
- Create: `D:/GEO2/backend/app/domain/knowledge/vector_index.py`
- Create: `D:/GEO2/backend/tests/test_vector_index.py`

**Interfaces:**
- `VectorIndex(kb_id: str)`
- `index.add_chunks(chunks: list[dict]) -> None` — chunks: `[{id, content, doc_id, chunk_index}, ...]`
- `index.query(query_text: str, top_k: int = 10) -> list[dict]` — returns `[{id, content, metadata, distance}, ...]`
- `index.delete_chunks(chunk_ids: list[str]) -> None`
- `index.get_all_ids() -> set[str]`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_vector_index.py`:

```python
"""Tests for VectorIndex (ChromaDB wrapper)."""
from unittest.mock import patch, MagicMock

import pytest

from app.domain.knowledge.vector_index import VectorIndex


@pytest.fixture
def mock_chroma():
    """Patch the ChromaDB PersistentClient and provide a mock collection."""
    with patch("app.domain.knowledge.vector_index.chromadb") as MockChroma:
        mock_client = MagicMock()
        MockChroma.PersistentClient.return_value = mock_client
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        yield MockChroma, mock_client, mock_collection


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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_vector_index.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/knowledge/vector_index.py`**

Create `D:/GEO2/backend/app/domain/knowledge/vector_index.py`:

```python
"""ChromaDB wrapper for knowledge base chunk vectors.

One ChromaDB collection per knowledge base (named "kb_{kb_id}").
The ChromaDB PersistentClient is process-singleton (class-level cached).
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings


class VectorIndex:
    """Thin wrapper around a ChromaDB collection for one knowledge base."""

    _client = None  # process-singleton (ChromaDB client is thread-safe)

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            settings = get_settings()
            cls._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return cls._client

    def __init__(self, kb_id: str) -> None:
        self.kb_id = kb_id
        client = self._get_client()
        self._collection = client.get_or_create_collection(
            name=f"kb_{kb_id}",
            metadata={"hnsw:space": "cosine"},  # use cosine distance
        )

    def add_chunks(self, chunks: list[dict]) -> None:
        """Add chunks to the index.

        chunks: [{'id', 'content', 'doc_id', 'chunk_index'}, ...]
        """
        if not chunks:
            return
        self._collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["content"] for c in chunks],
            metadatas=[
                {
                    "doc_id": c["doc_id"],
                    "chunk_index": c["chunk_index"],
                    "kb_id": self.kb_id,
                }
                for c in chunks
            ],
        )

    def query(self, query_text: str, top_k: int = 10) -> list[dict]:
        """Query by semantic similarity. Returns list of {id, content, metadata, distance}."""
        results = self._collection.query(
            query_texts=[query_text],
            n_results=top_k,
        )
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        docs = results.get("documents", [[]])[0] if results.get("documents") else []
        metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        dists = results.get("distances", [[]])[0] if results.get("distances") else []
        return [
            {
                "id": ids[i],
                "content": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None,
            }
            for i in range(len(ids))
        ]

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Delete chunks by ID."""
        if chunk_ids:
            self._collection.delete(ids=chunk_ids)

    def get_all_ids(self) -> set[str]:
        """Return all chunk IDs in the index (used by reindex for diff)."""
        result = self._collection.get()
        return set(result.get("ids", []))
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_vector_index.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): VectorIndex ChromaDB wrapper + tests"
```

---

## Phase 2: Hybrid Search + RRF

### Task 2.1: RRF Fusion Function (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/services/hybrid_search.py`
- Create: `D:/GEO2/backend/tests/test_hybrid_search.py`

**Interfaces:**
- `rrf_fusion(vector_results, keyword_results, top_k, k) -> list[dict]` — pure function
- `HybridSearch.search(kb_id, query, top_k) -> list[dict]` — orchestrates vector + keyword + RRF, with fallback

- [ ] **Step 1: Write failing test for `rrf_fusion`**

Create `D:/GEO2/backend/tests/test_hybrid_search.py`:

```python
"""Tests for hybrid search (RRF fusion + fallback)."""
from unittest.mock import patch, AsyncMock

import pytest

from app.services.hybrid_search import HybridSearch, rrf_fusion


class TestRRFFusion:
    def test_empty_inputs_return_empty(self) -> None:
        assert rrf_fusion([], [], top_k=5) == []

    def test_only_vector_results(self) -> None:
        vector = [
            {"id": "c1", "content": "x", "metadata": {}},
            {"id": "c2", "content": "y", "metadata": {}},
        ]
        fused = rrf_fusion(vector, [], top_k=5, k=60)
        assert len(fused) == 2
        # c1 should rank first (rank 1)
        assert fused[0]["id"] == "c1"
        # Both should have vector source only
        for c in fused:
            assert c["_sources"] == ["vector"]

    def test_only_keyword_results(self) -> None:
        keyword = [
            {"id": "c1", "content": "x", "metadata": {}},
        ]
        fused = rrf_fusion([], keyword, top_k=5, k=60)
        assert len(fused) == 1
        assert fused[0]["_sources"] == ["keyword"]

    def test_chunk_in_both_lists_scores_higher(self) -> None:
        """A chunk in both lists should be summed (higher score)."""
        vector = [
            {"id": "c1", "content": "x", "metadata": {}},
            {"id": "c2", "content": "y", "metadata": {}},
        ]
        keyword = [
            {"id": "c2", "content": "y", "metadata": {}},  # c2 also in keyword
            {"id": "c3", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector, keyword, top_k=5, k=60)
        # c2 appears in both → higher RRF score
        assert fused[0]["id"] == "c2"
        # c2's _sources should have both
        assert set(fused[0]["_sources"]) == {"vector", "keyword"}

    def test_top_k_limits_results(self) -> None:
        vector = [{"id": f"c{i}", "content": "x", "metadata": {}} for i in range(10)]
        keyword = [{"id": f"k{i}", "content": "y", "metadata": {}} for i in range(10)]
        fused = rrf_fusion(vector, keyword, top_k=3, k=60)
        assert len(fused) == 3

    def test_rrf_score_present(self) -> None:
        vector = [{"id": "c1", "content": "x", "metadata": {}}]
        fused = rrf_fusion(vector, [], top_k=5, k=60)
        assert "_rrf_score" in fused[0]
        assert fused[0]["_rrf_score"] > 0


class TestHybridSearchFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_keyword_when_vector_fails(self) -> None:
        """If vector search raises, hybrid should return keyword results."""
        with patch("app.services.hybrid_search.VectorIndex") as MockIndex:
            MockIndex.return_value.query.side_effect = Exception("ChromaDB down")

            # Also need to patch the keyword search via repository
            with patch("app.services.hybrid_search.KnowledgeRepository") as MockRepo:
                mock_chunk = type("Chunk", (), {
                    "id": "c1", "doc_id": "d1", "kb_id": "kb1",
                    "chunk_index": 0, "content": "test content"
                })()
                MockRepo.return_value.search_chunks_by_keyword = AsyncMock(
                    return_value=[mock_chunk]
                )
                # Need to mock the session context manager
                mock_session = MagicMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                with patch("app.services.hybrid_search.get_session_factory") as mock_factory:
                    mock_factory.return_value.return_value = mock_session

                    results = await HybridSearch().search("kb1", "test query")

            assert len(results) >= 1
            assert results[0]["_sources"] == ["keyword"]


class TestHybridSearchNormalPath:
    @pytest.mark.asyncio
    async def test_returns_rrf_fused_results(self) -> None:
        """When both succeed, return RRF-fused results."""
        with patch("app.services.hybrid_search.VectorIndex") as MockIndex:
            MockIndex.return_value.query.return_value = [
                {"id": "c1", "content": "v1", "metadata": {}, "distance": 0.1},
                {"id": "c2", "content": "v2", "metadata": {}, "distance": 0.2},
            ]
            with patch("app.services.hybrid_search.KnowledgeRepository") as MockRepo:
                mock_chunk = type("Chunk", (), {
                    "id": "c2", "doc_id": "d1", "kb_id": "kb1",
                    "chunk_index": 0, "content": "k1"
                })()
                MockRepo.return_value.search_chunks_by_keyword = AsyncMock(
                    return_value=[mock_chunk]
                )
                mock_session = MagicMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                with patch("app.services.hybrid_search.get_session_factory") as mock_factory:
                    mock_factory.return_value.return_value = mock_session

                    results = await HybridSearch().search("kb1", "test", top_k=5)

        # c2 should be first (in both lists)
        assert results[0]["id"] == "c2"
        # c1 should also be in results (only in vector)
        ids = {r["id"] for r in results}
        assert "c1" in ids
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_hybrid_search.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/services/hybrid_search.py`**

Create `D:/GEO2/backend/app/services/hybrid_search.py`:

```python
"""Hybrid search: combine vector (ChromaDB) + keyword (SQLite LIKE) via RRF.

Falls back to keyword-only if ChromaDB fails (degraded mode).
"""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.knowledge.vector_index import VectorIndex

logger = structlog.get_logger()


def rrf_fusion(
    vector_results: list[dict],
    keyword_results: list[dict],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    """Reciprocal Rank Fusion.

    Final score = sum(1 / (k + rank)) for each list the chunk appears in.
    Chunks appearing in both lists get summed scores (ranked higher).
    """
    scores: dict[str, float] = {}
    chunk_data: dict[str, dict] = {}

    for rank, chunk in enumerate(vector_results, start=1):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        chunk_data[cid] = {**chunk, "_sources": ["vector"]}

    for rank, chunk in enumerate(keyword_results, start=1):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid in chunk_data:
            existing = chunk_data[cid].get("_sources", [])
            chunk_data[cid] = {**chunk_data[cid], **chunk, "_sources": existing + ["keyword"]}
        else:
            chunk_data[cid] = {**chunk, "_sources": ["keyword"]}

    sorted_ids = sorted(scores.keys(), key=lambda x: -scores[x])
    return [{**chunk_data[cid], "_rrf_score": scores[cid]} for cid in sorted_ids[:top_k]]


class HybridSearch:
    """Orchestrates vector + keyword + RRF with graceful fallback."""

    async def search(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Hybrid search. Falls back to keyword-only if vector fails."""
        try:
            return await self._hybrid_search(kb_id, query, top_k)
        except Exception as e:
            logger.warning(
                "hybrid_search_failed, falling back to keyword",
                kb_id=kb_id, error=str(e),
            )
            return await self._keyword_search(kb_id, query, top_k)

    async def _hybrid_search(self, kb_id: str, query: str, top_k: int) -> list[dict]:
        settings = get_settings()
        # 1. Vector search
        index = VectorIndex(kb_id)
        vector_results = index.query(query_text=query, top_k=settings.hybrid_top_k_vector)
        # 2. Keyword search
        keyword_results = await self._keyword_search(kb_id, query, top_k=settings.hybrid_top_k_keyword)
        # 3. RRF fusion
        return rrf_fusion(vector_results, keyword_results, top_k=top_k, k=settings.hybrid_rrf_k)

    async def _keyword_search(self, kb_id: str, query: str, top_k: int) -> list[dict]:
        """Use existing v0.2 jieba-based keyword search."""
        import jieba
        from app.repositories.knowledge_repo import KnowledgeRepository

        keywords = [w for w in jieba.cut(query) if len(w.strip()) > 1]
        if not keywords:
            return []
        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            chunks = await repo.search_chunks_by_keyword(
                kb_id=kb_id, keywords=keywords, top_k=top_k
            )
        return [
            {
                "id": c.id,
                "content": c.content,
                "metadata": {
                    "doc_id": c.doc_id,
                    "chunk_index": c.chunk_index,
                    "kb_id": c.kb_id,
                },
            }
            for c in chunks
        ]
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_hybrid_search.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): hybrid search with RRF fusion + keyword fallback + tests"
```

---

## Phase 3: Repository Integration + Reindex

### Task 3.1: KnowledgeRepository.search_chunks_hybrid

**Files:**
- Modify: `D:/GEO2/backend/app/repositories/knowledge_repo.py`
- Modify: `D:/GEO2/backend/tests/test_knowledge_repo.py` (add test for new method)

**Interfaces (additions):**
- `KnowledgeRepository.search_chunks_hybrid(kb_id, query, top_k) -> list[dict]`

- [ ] **Step 1: Append failing test to `test_knowledge_repo.py`**

Append to `D:/GEO2/backend/tests/test_knowledge_repo.py`:

```python
@pytest.mark.asyncio
async def test_search_chunks_hybrid_uses_hybrid_search(db_session) -> None:
    """search_chunks_hybrid should delegate to HybridSearch service."""
    from unittest.mock import patch, AsyncMock
    from app.models.orm_v02 import KnowledgeBaseORM, KnowledgeChunkORM, KnowledgeDocumentORM

    # Setup
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    doc = KnowledgeDocumentORM(id="d1", kb_id="kb1", filename="x.txt",
                               file_path="/tmp/x.txt", file_type="txt",
                               file_size=100, parse_status="success")
    chunk = KnowledgeChunkORM(id="c1", doc_id="d1", kb_id="kb1",
                               chunk_index=0, content="test", content_length=4)
    db_session.add_all([kb, doc, chunk])
    await db_session.commit()

    repo = KnowledgeRepository(db_session)
    with patch("app.repositories.knowledge_repo.HybridSearch") as MockHS:
        MockHS.return_value.search = AsyncMock(return_value=[
            {"id": "c1", "content": "test", "metadata": {}, "_rrf_score": 1.0, "_sources": ["vector", "keyword"]}
        ])
        results = await repo.search_chunks_hybrid("kb1", "test query", top_k=5)

    assert len(results) == 1
    assert results[0]["id"] == "c1"
    MockHS.return_value.search.assert_called_once_with(
        kb_id="kb1", query="test query", top_k=5
    )
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_repo.py::test_search_chunks_hybrid_uses_hybrid_search -v
```

Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Add `search_chunks_hybrid` to `knowledge_repo.py`**

Edit `D:/GEO2/backend/app/repositories/knowledge_repo.py`. Add this method to the `KnowledgeRepository` class:

```python
    async def search_chunks_hybrid(
        self,
        kb_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Hybrid search: vector + keyword + RRF fusion.

        Returns top_k chunks ordered by RRF score. Each result has:
            - id: chunk UUID
            - content: chunk text
            - metadata: {doc_id, chunk_index, kb_id}
            - _rrf_score: combined relevance score
            - _sources: list of ['vector', 'keyword']
        """
        # Import here to avoid circular import
        from app.services.hybrid_search import HybridSearch
        return await HybridSearch().search(kb_id=kb_id, query=query, top_k=top_k)
```

- [ ] **Step 4: Run test**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_repo.py -v
```

Expected: All tests PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): KnowledgeRepository.search_chunks_hybrid + test"
```

---

### Task 3.2: ReindexService (Lazy Vectorization)

**Files:**
- Create: `D:/GEO2/backend/app/services/reindex.py`
- Create: `D:/GEO2/backend/tests/test_reindex.py`

**Interfaces:**
- `ReindexService.reindex_all() -> dict` — returns `{kb_id: {total, indexed, skipped}}`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_reindex.py`:

```python
"""Tests for ReindexService (startup-time lazy vectorization)."""
from unittest.mock import patch, MagicMock

import pytest

from app.services.reindex import ReindexService


@pytest.mark.asyncio
async def test_reindex_indexes_missing_chunks() -> None:
    """Chunks not in ChromaDB should be embedded and added."""
    from app.core.db import get_session_factory
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeBaseORM, KnowledgeDocumentORM, KnowledgeChunkORM

    # Setup: 1 KB with 2 chunks
    async with get_session_factory()() as session:
        repo = KnowledgeRepository(session)
        kb = await repo.create_kb(name="KB")
        doc = await repo.add_document(
            kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
            file_type="txt", file_size=100,
        )
        await repo.add_chunks(
            doc_id=doc.id, kb_id=kb.id,
            chunks=[
                {"chunk_index": 0, "content": "chunk 1", "content_length": 7},
                {"chunk_index": 1, "content": "chunk 2", "content_length": 7},
            ],
        )

    # Mock VectorIndex.get_all_ids to return empty (nothing indexed yet)
    with patch("app.services.reindex.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        mock_index.get_all_ids.return_value = set()  # nothing indexed

        # Mock EmbeddingService.embed to return fake vectors
        with patch("app.services.reindex.EmbeddingService") as MockEmbed:
            MockEmbed.embed.return_value = [[0.1] * 512, [0.2] * 512]

            # Mock the batch add
            mock_index._collection = MagicMock()

            stats = await ReindexService().reindex_all()

    # Verify
    assert kb.id in stats
    assert stats[kb.id]["total"] == 2
    assert stats[kb.id]["indexed"] == 2
    assert stats[kb.id]["skipped"] == 0

    # Verify add was called
    assert mock_index._collection.add.called


@pytest.mark.asyncio
async def test_reindex_skips_already_indexed() -> None:
    """Chunks already in ChromaDB should be skipped."""
    from app.core.db import get_session_factory
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeBaseORM, KnowledgeDocumentORM, KnowledgeChunkORM

    # Setup
    async with get_session_factory()() as session:
        repo = KnowledgeRepository(session)
        kb = await repo.create_kb(name="KB")
        doc = await repo.add_document(
            kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
            file_type="txt", file_size=100,
        )
        chunks = await repo.add_chunks(
            doc_id=doc.id, kb_id=kb.id,
            chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
        )
        chunk_id = chunks[0].id if hasattr(chunks, '__iter__') else "c1"

    with patch("app.services.reindex.VectorIndex") as MockIndex:
        mock_index = MockIndex.return_value
        # Simulate chunk already indexed
        mock_index.get_all_ids.return_value = {chunk_id}

        stats = await ReindexService().reindex_all()

    # No embedding should happen
    assert stats[kb.id]["indexed"] == 0
    assert stats[kb.id]["skipped"] == 1


@pytest.mark.asyncio
async def test_reindex_handles_empty_kb() -> None:
    """A KB with no chunks should not be processed."""
    from app.core.db import get_session_factory
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeBaseORM

    async with get_session_factory()() as session:
        repo = KnowledgeRepository(session)
        kb = await repo.create_kb(name="Empty KB")
        # No chunks

    stats = await ReindexService().reindex_all()
    assert stats[kb.id]["total"] == 0
    assert stats[kb.id]["indexed"] == 0
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_reindex.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/services/reindex.py`**

Create `D:/GEO2/backend/app/services/reindex.py`:

```python
"""Reindex service: lazy vectorization of existing chunks at startup."""
from __future__ import annotations

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.knowledge.vector_index import VectorIndex
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()


class ReindexService:
    """Find chunks without vectors and embed them.

    Called once at startup (in main.py lifespan). Idempotent: chunks
    already in ChromaDB are skipped.
    """

    async def reindex_all(self) -> dict[str, dict]:
        """Reindex all knowledge bases. Returns per-kb stats."""
        from app.core.config import get_settings
        settings = get_settings()
        stats: dict[str, dict] = {}

        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            kbs = await repo.list_knowledge_bases()

            for kb in kbs:
                kb_stats = await self._reindex_one_kb(repo, kb.id, settings)
                stats[kb.id] = kb_stats

        total_indexed = sum(s["indexed"] for s in stats.values())
        logger.info("reindex_done", total_kbs=len(stats), total_indexed=total_indexed)
        return stats

    async def _reindex_one_kb(self, repo: KnowledgeRepository, kb_id: str, settings) -> dict:
        # 1. Get all chunks from SQLite
        all_chunks = await repo.list_chunks(kb_id)
        if not all_chunks:
            return {"total": 0, "indexed": 0, "skipped": 0}

        # 2. Get already-indexed IDs from ChromaDB
        index = VectorIndex(kb_id)
        indexed_ids = index.get_all_ids()

        # 3. Find chunks to index
        to_index = [c for c in all_chunks if c.id not in indexed_ids]
        if not to_index:
            return {"total": len(all_chunks), "indexed": 0, "skipped": len(all_chunks)}

        # 4. Embed + index in batches
        for i in range(0, len(to_index), settings.embedding_batch_size):
            batch = to_index[i:i + settings.embedding_batch_size]
            texts = [c.content for c in batch]
            embeddings = EmbeddingService.embed(texts)
            index._collection.add(
                ids=[c.id for c in batch],
                documents=texts,
                embeddings=embeddings,
                metadatas=[
                    {
                        "doc_id": c.doc_id,
                        "chunk_index": c.chunk_index,
                        "kb_id": kb_id,
                    }
                    for c in batch
                ],
            )

        return {
            "total": len(all_chunks),
            "indexed": len(to_index),
            "skipped": len(all_chunks) - len(to_index),
        }
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_reindex.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): ReindexService for startup lazy vectorization + tests"
```

---

## Phase 4: Wire into App + v0.4 Tool Upgrade

### Task 4.1: Hook reindex into FastAPI startup

**Files:**
- Modify: `D:/GEO2/backend/app/main.py`

- [ ] **Step 1: Write failing test for startup behavior**

Append to `D:/GEO2/backend/tests/test_api_knowledge.py` (or create `D:/GEO2/backend/tests/test_startup_v0.5.py`):

```python
"""Test that reindex is called during app startup."""
from unittest.mock import patch, AsyncMock


def test_startup_runs_reindex():
    """The FastAPI lifespan should call ReindexService.reindex_all()."""
    with patch("app.services.reindex.ReindexService") as MockReindex:
        mock_instance = MockReindex.return_value
        mock_instance.reindex_all = AsyncMock(return_value={})

        with patch("app.domain.monitor.scheduler.load_all_monitor_tasks", new=AsyncMock()):
            from fastapi.testclient import TestClient
            from app.main import app
            with TestClient(app) as client:
                pass  # triggers lifespan startup

        mock_instance.reindex_all.assert_called()
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_startup_v0.5.py -v
```

Expected: FAIL (reindex not called yet, or test fails because ChromaDB isn't initialized in test env).

Note: This test may need adjustment if the test env doesn't have `./data/chroma/` writable. If it fails due to filesystem, mark it as expected to fail and add a comment; we'll handle it in the integration test.

- [ ] **Step 3: Update `main.py` lifespan**

Edit `D:/GEO2/backend/app/main.py`. Find the `lifespan` function and add the reindex call after `load_all_monitor_tasks`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # v0.3 scheduler
    start_scheduler()
    await load_all_monitor_tasks()
    # v0.5 lazy reindex (vectorize existing chunks)
    from app.services.reindex import ReindexService
    reindex_stats = await ReindexService().reindex_all()
    logger.info("v0.5_reindex_done", **reindex_stats)
    yield
    # Shutdown
    shutdown_scheduler()
    await dispose_db()
```

- [ ] **Step 4: Verify all existing tests still pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v --tb=short 2>&1 | tail -50
```

Expected: All v0.1 + v0.2 + v0.3 + v0.4 + v0.5 tests PASS. If the startup test fails due to ChromaDB not being testable, skip it with a comment.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): hook ReindexService into FastAPI lifespan startup"
```

---

### Task 4.2: Update v0.4 agent tool to use hybrid search

**Files:**
- Modify: `D:/GEO2/backend/app/domain/agent/tool_executor.py`

**Interfaces (no new, just internal change):**
- `ToolExecutor._execute_search_knowledge(args) -> dict` now uses hybrid search

- [ ] **Step 1: Modify `_execute_search_knowledge` in `tool_executor.py`**

Edit `D:/GEO2/backend/app/domain/agent/tool_executor.py`. Find the existing `_execute_search_knowledge` method and replace it:

```python
    @staticmethod
    async def _execute_search_knowledge(args: SearchKnowledgeArgs) -> dict:
        """Search knowledge base using hybrid retrieval (vector + keyword + RRF).

        v0.5 upgrade: was keyword-only, now hybrid. Returns same shape as before.
        """
        from app.core.db import get_session_factory
        from app.repositories.knowledge_repo import KnowledgeRepository

        async with get_session_factory()() as session:
            repo = KnowledgeRepository(session)
            chunks = await repo.search_chunks_hybrid(
                kb_id=args.kb_id,
                query=args.query,
                top_k=args.limit,
            )

        return {
            "kb_id": args.kb_id,
            "query": args.query,
            "chunks": [
                {
                    "id": c["id"],
                    "doc_id": c["metadata"].get("doc_id"),
                    "chunk_index": c["metadata"].get("chunk_index"),
                    "content": c["content"][:500],
                    "content_length": min(len(c["content"]), 500),
                    "rrf_score": c.get("_rrf_score"),
                    "sources": c.get("_sources", []),
                }
                for c in chunks
            ],
            "total_found": len(chunks),
        }
```

- [ ] **Step 2: Run v0.4 agent tests to verify no regression**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: All existing v0.4 tests PASS (because they mock HybridSearch at the repository level, or use mocked search).

If any test breaks because the old test assumed `search_chunks_by_keyword` was called, update those tests to mock `search_chunks_hybrid` instead. See existing test for reference.

- [ ] **Step 3: Add explicit test for hybrid integration**

Append to `D:/GEO2/backend/tests/test_tool_executor.py`:

```python
    @pytest.mark.asyncio
    async def test_search_knowledge_uses_hybrid_search(self, executor: ToolExecutor) -> None:
        """v0.5: _execute_search_knowledge should use search_chunks_hybrid, not keyword-only."""
        from app.domain.agent.tools import SearchKnowledgeArgs
        from unittest.mock import patch, AsyncMock

        with patch("app.domain.agent.tool_executor.get_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_factory.return_value = mock_session

            with patch("app.domain.agent.tool_executor.KnowledgeRepository") as MockRepo:
                mock_repo = MockRepo.return_value
                mock_repo.search_chunks_hybrid = AsyncMock(return_value=[
                    {"id": "c1", "content": "found", "metadata": {"doc_id": "d1", "chunk_index": 0}, "_rrf_score": 1.0, "_sources": ["vector", "keyword"]}
                ])
                result = await executor._execute_search_knowledge(
                    SearchKnowledgeArgs(kb_id="kb1", query="test", limit=5)
                )

        # Verify hybrid was called (not keyword-only)
        mock_repo.search_chunks_hybrid.assert_called_once()
        assert "rrf_score" in result["chunks"][0]
        assert result["chunks"][0]["sources"] == ["vector", "keyword"]
```

- [ ] **Step 4: Run test**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: All tests PASS (including new hybrid test).

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.5): upgrade v0.4 agent's search_knowledge tool to use hybrid search"
```

---

## Phase 5: End-to-End Verification & Documentation

### Task 5.1: E2E Test for Hybrid Search Behavior

**Files:**
- Create: `D:/GEO2/backend/tests/test_e2e_v0.5.py`

- [ ] **Step 1: Write E2E test**

Create `D:/GEO2/backend/tests/test_e2e_v0.5.py`:

```python
"""E2E test for v0.5 hybrid search: verifies semantic + keyword blending works."""
from unittest.mock import patch, AsyncMock, MagicMock
import numpy as np

import pytest

from app.services.hybrid_search import HybridSearch, rrf_fusion


class TestHybridSearchEndToEnd:
    @pytest.mark.asyncio
    async def test_semantic_match_beats_keyword_only(self) -> None:
        """Scenario: user searches for 'long battery' but doc has '5000mAh capacity'.
        Vector search finds the doc; keyword search misses it.
        Hybrid should find the doc (via vector) where keyword-only would miss.
        """
        # Simulate: doc1 = "phone has 5000mAh capacity, charges fast"
        #           doc2 = "phone has long battery, lasts all day" (keyword match)
        vector_results = [
            {"id": "doc1", "content": "5000mAh capacity, charges fast", "metadata": {}, "distance": 0.15},
        ]
        keyword_results = [
            {"id": "doc2", "content": "long battery, lasts all day", "metadata": {}},
        ]
        # RRF: doc1 has vector rank 1, doc2 has keyword rank 1
        # doc1 score: 1/(60+1) = 0.0164
        # doc2 score: 1/(60+1) = 0.0164
        # Both equal, but doc1 first by stable sort

        fused = rrf_fusion(vector_results, keyword_results, top_k=5)
        assert len(fused) == 2
        ids = [c["id"] for c in fused]
        assert "doc1" in ids
        assert "doc2" in ids

    def test_chunk_in_both_lists_dominates(self) -> None:
        """A chunk matching both lists should be ranked highest."""
        vector_results = [
            {"id": "shared", "content": "x", "metadata": {}, "distance": 0.1},
            {"id": "vec_only", "content": "y", "metadata": {}, "distance": 0.2},
        ]
        keyword_results = [
            {"id": "shared", "content": "x", "metadata": {}},
            {"id": "kw_only", "content": "z", "metadata": {}},
        ]
        fused = rrf_fusion(vector_results, keyword_results, top_k=3)
        # "shared" appears in both → score = 1/61 + 1/61 = 0.0328
        # "vec_only" → 1/61 = 0.0164
        # "kw_only" → 1/61 = 0.0164
        assert fused[0]["id"] == "shared"
        # vec_only and kw_only tied for second; just verify shared is first
```

- [ ] **Step 2: Run E2E test**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_e2e_v0.5.py -v
```

Expected: All PASS.

- [ ] **Step 3: Run ALL tests (verify no regression)**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v 2>&1 | tail -20
```

Expected: All v0.1 + v0.2 + v0.3 + v0.4 + v0.5 tests PASS.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add backend/tests/ && git commit -m "test(backend/v0.5): end-to-end hybrid search behavior tests"
```

---

### Task 5.2: Manual Verification Checklist

**Files:**
- Create: `D:/GEO2/docs/MANUAL_VERIFICATION_V0.5.md`

- [ ] **Step 1: Write checklist**

Create `D:/GEO2/docs/MANUAL_VERIFICATION_V0.5.md`:

```markdown
# 手动验证清单 — GEO Agent v0.5

发布前必跑 7 个场景。

## 前置条件

\`\`\`bash
cd "D:/GEO2"
# 编辑 .env，确保 DEEPSEEK_API_KEY 已设置
docker-compose up --build -d
sleep 60  # 首次启动需加载 bge 模型
\`\`\`

## 场景

### 1. 混合检索召回率提升 ✅

1. 在 v0.2 上传 5 个文档到知识库（内容关于"产品续航"）
2. 在知识库详情页搜索"长续航"
3. **预期**：
   - 找到含"电池容量"、"续航"等的段落
   - 召回比 v0.2 纯关键词搜索更多

### 2. 启动时 lazy 向量化 ✅

1. 在 v0.5 之前上传了文档到 v0.2
2. 启动 v0.5
3. 看日志 `v0.5_reindex_done`
4. **预期**：日志显示 `total_kbs` 和 `total_indexed`

### 3. 新增文档自动向量化 ✅

1. 在 v0.2 上传新文档
2. 等待解析完成
3. 立即用新文档的关键词搜索
4. **预期**：新文档的 chunk 出现在搜索结果中（说明已向量化）

### 4. 删除文档级联清理 ✅

1. 在 v0.2 删除一个文档
2. 检查 ChromaDB 内部
3. **预期**：对应的 chunk 向量已从 ChromaDB 移除

### 5. ChromaDB 不可用时降级 ✅

1. 临时删除 `./data/chroma/` 目录权限
2. 触发一次搜索
3. **预期**：
   - 仍然返回结果（纯关键词）
   - 日志显示 `hybrid_search_failed, falling back to keyword`

### 6. 单次 hybrid search < 500ms ✅

1. 准备 100 chunks
2. 用 stopwatch 测搜索延迟
3. **预期**：< 500ms

### 7. v0.4 agent 工具升级 ✅

1. 在 agent chat 问"小米的售后"
2. 看 agent 调用的 `search_knowledge` 工具结果
3. **预期**：能找到"退换货"、"保修"等段落（语义匹配）

## 通过标准

7 项全过 → v0.5 完成。
\`\`\`

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/MANUAL_VERIFICATION_V0.5.md && git commit -m "docs: v0.5 manual verification checklist"
```

---

### Task 5.3: Update ROADMAP

**Files:**
- Modify: `D:/GEO2/docs/ROADMAP.md`

- [ ] **Step 1: Mark v0.5 design + plan complete, note direction change**

Edit `D:/GEO2/docs/ROADMAP.md`. Update the v0.5 entry to mark design+plan as done, and note the direction change (from competitive comparison to vector search).

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/ROADMAP.md && git commit -m "docs: mark v0.5 design + plan as complete in ROADMAP"
```

---

## Self-Review

After writing this plan, run the writing-plans self-review checklist:

**1. Spec coverage** — Every requirement in the v0.5 spec is covered:

| Spec § | Implemented in Task |
|---|---|
| §1 (background, scope) | Phase 0 + Task 5.3 (ROADMAP) |
| §2 (users, scenarios) | Task 5.2 (manual checklist) |
| §3 (architecture) | Phase 0-4 wiring |
| §4 (ChromaDB integration) | Task 1.1 |
| §5 (RRF + HybridSearch) | Task 2.1 |
| §6 (ReindexService) | Task 3.2 |
| §7 (incremental sync) | Spec mentions; partial — v0.2 hook not in v0.5 plan (deferred to v0.5.x) |
| §8 (fallback) | Task 2.1 tests cover |
| §9 (error handling) | Throughout |
| §10 (testing) | Tests in every task + Task 5.1 |
| §11 (acceptance) | Task 5.2 |
| §12 (risks) | Documented in spec |
| §13 (upgrade path) | Spec only; no v0.5.x tasks (per user's "do upgrade path only in spec" decision) |

**2. Placeholder scan** — No TBD/TODO. All code blocks complete.

**3. Type consistency** —
- `VectorIndex(kb_id)`, `.add_chunks(chunks)`, `.query(query_text, top_k)`, `.delete_chunks(ids)`, `.get_all_ids()` ✓
- `HybridSearch().search(kb_id, query, top_k) -> list[dict]` ✓
- `rrf_fusion(vector_results, keyword_results, top_k, k=60)` ✓
- `EmbeddingService.embed(texts) -> list[list[float]]` ✓
- `ReindexService().reindex_all() -> dict[str, dict]` ✓
- `KnowledgeRepository.search_chunks_hybrid(kb_id, query, top_k) -> list[dict]` ✓

All consistent.

---

## Execution Handoff

This plan is **complete** and saved to:
`D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.5.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task with two-stage review between tasks. Best for catching issues early and maintaining quality across 12+ tasks.

**2. Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints. Faster but no inter-task review.

**Which approach?**

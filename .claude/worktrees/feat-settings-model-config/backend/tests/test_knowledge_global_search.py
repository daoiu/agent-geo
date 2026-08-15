"""v0.6 P1.3 — Cross-KB hybrid search tests.

Covers:
1. repo.search_chunks_all_keywords — joins chunks+documents+bases, ranks by
   keyword count, attaches kb_name + doc_filename
2. HybridSearch.search_across_kbs — runs vector loop + global keyword,
   RRF-fuses, returns hits with metadata.kb_name
3. GET /knowledge/search — validates q (no kb_id), returns GlobalKnowledgeSearchResult
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models.knowledge import GlobalKnowledgeSearchResult
from app.models.orm_v02 import (
    KnowledgeBaseORM,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
)
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.hybrid_search import HybridSearch


# -------------------- repo --------------------


@pytest.mark.asyncio
async def test_search_chunks_all_keywords_joins_kb_and_doc(db_session):
    repo = KnowledgeRepository(db_session)
    kb1 = await repo.create_kb(name="KB-甲")
    kb2 = await repo.create_kb(name="KB-乙")
    d1 = await repo.add_document(
        kb_id=kb1.id, filename="a.md", file_path="/tmp/a.md",
        file_type="md", file_size=10,
    )
    d2 = await repo.add_document(
        kb_id=kb2.id, filename="b.md", file_path="/tmp/b.md",
        file_type="md", file_size=10,
    )
    await repo.add_chunks(
        doc_id=d1.id, kb_id=kb1.id,
        chunks=[{"chunk_index": 0, "content": "云吞皮薄爆汁", "content_length": 6}],
    )
    await repo.add_chunks(
        doc_id=d2.id, kb_id=kb2.id,
        chunks=[{"chunk_index": 0, "content": "云吞皮薄云吞皮薄云吞皮薄", "content_length": 12}],
    )

    hits = await repo.search_chunks_all_keywords(keywords=["云吞"], top_k=10)

    assert len(hits) == 2
    # 多次出现应该排前面
    assert hits[0]["chunk"].kb_id == kb2.id
    assert hits[0]["kb_name"] == "KB-乙"
    assert hits[0]["doc_filename"] == "b.md"
    assert hits[0]["score"] >= hits[1]["score"]


@pytest.mark.asyncio
async def test_search_chunks_all_keywords_empty_returns_empty(db_session):
    repo = KnowledgeRepository(db_session)
    assert await repo.search_chunks_all_keywords(keywords=[], top_k=10) == []


# -------------------- service (search_across_kbs) --------------------


@pytest.mark.asyncio
async def test_search_across_kbs_keyword_only_when_no_vector_index(db_session):
    """If VectorIndex raises, search_across_kbs still returns keyword hits."""
    from app.repositories.knowledge_repo import KnowledgeRepository as Repo

    kb = await Repo(db_session).create_kb(name="KB")

    # Patch VectorIndex to raise (simulate chroma unavailable / empty collection)
    with patch("app.services.hybrid_search.VectorIndex") as MockVI:
        MockVI.side_effect = Exception("chroma down")
        results = await HybridSearch().search_across_kbs(query="hello", top_k=5)

    # No docs added → empty list, but the call should not raise.
    assert results == []


@pytest.mark.asyncio
async def test_search_across_kbs_returns_enriched_metadata(db_session):
    """Hits should carry kb_name + doc_filename so the API can render attribution."""
    from app.repositories.knowledge_repo import KnowledgeRepository as Repo

    repo = Repo(db_session)
    kb1 = await repo.create_kb(name="北北云吞-KB")
    d1 = await repo.add_document(
        kb_id=kb1.id, filename="北北云吞.md",
        file_path="/tmp/x.md", file_type="md", file_size=10,
    )
    await repo.add_chunks(
        doc_id=d1.id, kb_id=kb1.id,
        chunks=[
            {"chunk_index": 0, "content": "陈皮马蹄捶打大肉云吞，玉林老城北总店",
             "content_length": 19},
        ],
    )

    # Force vector to no-op so keyword path dominates
    with patch("app.services.hybrid_search.VectorIndex") as MockVI:
        MockVI.side_effect = Exception("no vector index here")
        results = await HybridSearch().search_across_kbs(
            query="陈皮马蹄 玉林", top_k=5
        )

    assert len(results) >= 1
    hit = results[0]
    assert hit["metadata"]["kb_name"] == "北北云吞-KB"
    assert hit["metadata"]["doc_filename"] == "北北云吞.md"
    assert "vector" not in hit["_sources"]  # vector path failed → keyword-only
    assert "keyword" in hit["_sources"]
    assert hit["_rrf_score"] > 0


# -------------------- api --------------------


@pytest.fixture
async def app_client(db_session):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, app


@pytest.mark.asyncio
async def test_global_search_endpoint_no_kb_id_required(db_session, app_client, monkeypatch):
    ac, app = app_client

    # Insert fixtures via repo (one shared session for the lifespan).
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="北北云吞")
    doc = await repo.add_document(
        kb_id=kb.id, filename="北北云吞.md",
        file_path="/tmp/x.md", file_type="md", file_size=10,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{
            "chunk_index": 0,
            "content": "脆马蹄陈皮捶打大肉云吞，筒骨清汤",
            "content_length": 17,
        }],
    )

    # Disable vector path so the test stays hermetic to chroma
    monkeypatch.setattr(
        "app.services.hybrid_search.VectorIndex",
        lambda _kb_id: (_ for _ in ()).throw(Exception("no chroma in tests")),
    )

    resp = await ac.get("/api/knowledge/search", params={"q": "云吞 马蹄"})
    assert resp.status_code == 200, resp.text
    body = GlobalKnowledgeSearchResult(**resp.json())
    assert body.query == "云吞 马蹄"
    assert len(body.hits) >= 1
    hit = body.hits[0]
    assert hit.kb_name == "北北云吞"
    assert hit.doc_filename == "北北云吞.md"
    assert hit.chunk_id
    assert "keyword" in hit.sources


@pytest.mark.asyncio
async def test_global_search_endpoint_rejects_empty_query(app_client):
    ac, _ = app_client
    resp = await ac.get("/api/knowledge/search", params={"q": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_global_search_endpoint_rejects_oversized_limit(app_client):
    ac, _ = app_client
    resp = await ac.get("/api/knowledge/search",
                        params={"q": "hi", "limit": 999})
    assert resp.status_code == 422

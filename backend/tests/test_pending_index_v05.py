"""Tests for v0.5 pending_index column (spec §7 incremental sync)."""
import pytest
from sqlalchemy import select, text

from app.core.db import init_db
from app.models.orm_v02 import KnowledgeChunkORM


@pytest.mark.asyncio
async def test_knowledge_chunks_has_pending_index_column(db_session) -> None:
    """The pending_index column must exist on the knowledge_chunks table."""
    from app.core.db import get_engine
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(knowledge_chunks)"))
        columns = {row[1] for row in result.fetchall()}
    assert "pending_index" in columns


@pytest.mark.asyncio
async def test_knowledge_chunks_pending_index_defaults_to_false(db_session) -> None:
    """New chunks have pending_index=False by default."""
    from app.repositories.knowledge_repo import KnowledgeRepository
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=10,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "x", "content_length": 1}],
    )
    await db_session.commit()

    result = await db_session.execute(
        select(KnowledgeChunkORM).where(KnowledgeChunkORM.kb_id == kb.id)
    )
    chunks = list(result.scalars().all())
    assert len(chunks) == 1
    assert chunks[0].pending_index is False


@pytest.mark.asyncio
async def test_init_db_migration_is_idempotent() -> None:
    """Calling init_db twice does not raise (migration is idempotent)."""
    await init_db()
    await init_db()  # second call should be no-op

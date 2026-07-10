"""v0.5 pending_index 字段测试(spec §7 增量同步)。"""
import pytest
from sqlalchemy import select, text

from app.core.db import init_db
from app.models.orm_v02 import KnowledgeChunkORM


@pytest.mark.asyncio
async def test_knowledge_chunks_has_pending_index_column(db_session) -> None:
    """knowledge_chunks 表必须有 pending_index 列(由 init_db 迁移添加)。"""
    from app.core.db import get_engine
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(knowledge_chunks)"))
        columns = {row[1] for row in result.fetchall()}
    assert "pending_index" in columns


@pytest.mark.asyncio
async def test_knowledge_chunks_pending_index_defaults_to_false(db_session) -> None:
    """新建 chunk 的 pending_index 默认应为 False(已同步)。"""
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
    """init_db 重复调用不应报错(迁移幂等)。"""
    await init_db()
    await init_db()  # 第二次应是 no-op

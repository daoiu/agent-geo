"""一次性:清空所有 KB 的 Chroma collection + 触发 reindex。

清空后必须重置 VectorIndex._client 单例,否则 get_or_create_collection
会返回已删除 collection 的 stale 引用(详见 vector_index.py:17 单例警告)。
"""
import asyncio

from app.core.db import get_session_factory
from app.domain.knowledge.vector_index import VectorIndex
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.reindex import ReindexService


async def main():
    sf = get_session_factory()

    # 1) 列出所有 KB,逐个删 collection
    async with sf() as session:
        repo = KnowledgeRepository(session)
        kbs = await repo.list_kbs()
        kb_ids = [kb.id for kb in kbs]
    print(f"发现 {len(kb_ids)} 个 KB")

    client = VectorIndex._get_client()
    for kb_id in kb_ids:
        name = f"kb_{kb_id}"
        try:
            client.delete_collection(name)
            print(f"已删除 collection: {name}")
        except Exception as e:
            # collection 不存在时跳过
            print(f"跳过 {name}: {e}")

    # 2) 重置单例,否则下次 VectorIndex(kb_id) 会拿到 stale 对象
    VectorIndex._client = None
    print("已重置 VectorIndex._client 单例")

    # 3) reindex(走当前 EmbeddingService,512 维)
    stats = await ReindexService().reindex_all()
    print(f"reindex 完成: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
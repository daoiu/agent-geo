"""Repository for knowledge base, documents, and chunks."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v02 import (
    KnowledgeBaseORM,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
)


class KnowledgeRepository:
    """Data access for knowledge base tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Knowledge Base ---

    async def create_kb(
        self, name: str, description: str | None = None
    ) -> KnowledgeBaseORM:
        kb = KnowledgeBaseORM(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
        )
        self.session.add(kb)
        await self.session.commit()
        await self.session.refresh(kb)
        return kb

    async def get_kb(self, kb_id: str) -> KnowledgeBaseORM | None:
        result = await self.session.execute(
            select(KnowledgeBaseORM).where(KnowledgeBaseORM.id == kb_id)
        )
        return result.scalar_one_or_none()

    async def list_kbs(self) -> list[KnowledgeBaseORM]:
        result = await self.session.execute(
            select(KnowledgeBaseORM).order_by(KnowledgeBaseORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_kb(self, kb_id: str) -> None:
        """Cascade-deletes via FK ON DELETE CASCADE."""
        await self.session.execute(
            delete(KnowledgeBaseORM).where(KnowledgeBaseORM.id == kb_id)
        )
        await self.session.commit()

    # --- Documents ---

    async def add_document(
        self,
        kb_id: str,
        filename: str,
        file_path: str,
        file_type: str,
        file_size: int | None = None,
    ) -> KnowledgeDocumentORM:
        doc = KnowledgeDocumentORM(
            id=str(uuid.uuid4()),
            kb_id=kb_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            parse_status="pending",
            chunk_count=0,
        )
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def get_document(self, doc_id: str) -> KnowledgeDocumentORM | None:
        result = await self.session.execute(
            select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(self, kb_id: str) -> list[KnowledgeDocumentORM]:
        result = await self.session.execute(
            select(KnowledgeDocumentORM)
            .where(KnowledgeDocumentORM.kb_id == kb_id)
            .order_by(KnowledgeDocumentORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_document_status(
        self,
        doc_id: str,
        status: str,
        error: str | None = None,
        chunk_count: int | None = None,
    ) -> None:
        doc = await self.get_document(doc_id)
        if doc is None:
            return
        doc.parse_status = status
        if error is not None:
            doc.parse_error = error
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        await self.session.commit()

    # --- Chunks ---

    async def add_chunks(
        self, doc_id: str, kb_id: str, chunks: list[dict]
    ) -> int:
        """Bulk insert chunks. Returns count added."""
        rows = [
            KnowledgeChunkORM(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                kb_id=kb_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                content_length=c["content_length"],
            )
            for c in chunks
        ]
        self.session.add_all(rows)
        await self.session.commit()
        return len(rows)

    async def mark_chunks_pending(self, chunk_ids: list[str]) -> None:
        """v0.5: Set pending_index=True for given chunk ids. Used when ChromaDB sync fails."""
        if not chunk_ids:
            return
        from sqlalchemy import update
        await self.session.execute(
            update(KnowledgeChunkORM)
            .where(KnowledgeChunkORM.id.in_(chunk_ids))
            .values(pending_index=True)
        )
        await self.session.commit()

    async def list_chunk_ids_for_doc(self, doc_id: str) -> list[str]:
        """v0.5: Return all chunk IDs for a document (used by delete cascade)."""
        from sqlalchemy import select
        result = await self.session.execute(
            select(KnowledgeChunkORM.id).where(KnowledgeChunkORM.doc_id == doc_id)
        )
        return [row[0] for row in result.all()]

    async def list_chunks_for_doc(self, doc_id: str) -> list[KnowledgeChunkORM]:
        """v0.5: Return all chunks for a specific document (精确按 doc_id 查,不全表扫)。"""
        from sqlalchemy import select
        result = await self.session.execute(
            select(KnowledgeChunkORM)
            .where(KnowledgeChunkORM.doc_id == doc_id)
            .order_by(KnowledgeChunkORM.chunk_index)
        )
        return list(result.scalars().all())

    async def list_chunks(self, kb_id: str) -> list[KnowledgeChunkORM]:
        result = await self.session.execute(
            select(KnowledgeChunkORM)
            .where(KnowledgeChunkORM.kb_id == kb_id)
            .order_by(KnowledgeChunkORM.chunk_index)
        )
        return list(result.scalars().all())

    async def search_chunks_by_keyword(
        self, kb_id: str, keywords: list[str], top_k: int = 5
    ) -> list[KnowledgeChunkORM]:
        """Simple keyword matching: score by count of keyword occurrences.

        NOTE: this loads all chunks for the kb; fine for v0.2 sizes
        (hundreds of chunks). v0.5 will move to pgvector.
        """
        if not keywords:
            return []

        all_chunks = await self.list_chunks(kb_id)
        scored: list[tuple[int, KnowledgeChunkORM]] = []
        for chunk in all_chunks:
            score = sum(chunk.content.count(kw) for kw in keywords)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_k]]

    async def search_chunks_all_keywords(
        self, keywords: list[str], top_k: int = 50
    ) -> list[dict]:
        """Cross-KB keyword search (v0.6 P1.3).

        Joins chunks → documents → bases so each hit carries kb_name and
        doc_filename, which is what the global search UI needs to render
        attribution. Returns dict-shaped rows (lighter than ORM for the
        FusionService hot path).
        """
        if not keywords:
            return []

        rows = await self.session.execute(
            select(
                KnowledgeChunkORM,
                KnowledgeBaseORM.name.label("kb_name"),
                KnowledgeDocumentORM.filename.label("doc_filename"),
            )
            .join(
                KnowledgeBaseORM,
                KnowledgeBaseORM.id == KnowledgeChunkORM.kb_id,
            )
            .join(
                KnowledgeDocumentORM,
                KnowledgeDocumentORM.id == KnowledgeChunkORM.doc_id,
            )
        )

        scored: list[tuple[int, KnowledgeChunkORM, str, str]] = []
        for chunk, kb_name, doc_filename in rows.all():
            score = sum(chunk.content.count(kw) for kw in keywords)
            if score > 0:
                scored.append((score, chunk, kb_name, doc_filename))
        scored.sort(key=lambda x: (-x[0], x[1].created_at))

        return [
            {
                "chunk": chunk,
                "kb_id": chunk.kb_id,
                "kb_name": kb_name,
                "doc_id": chunk.doc_id,
                "doc_filename": doc_filename,
                "chunk_index": chunk.chunk_index,
                "score": score,
            }
            for score, chunk, kb_name, doc_filename in scored[:top_k]
        ]

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

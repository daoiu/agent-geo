"""Async worker for parsing uploaded documents into chunks."""
from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.exceptions import DocumentParseError
from app.domain.knowledge.chunker import chunk_text
from app.domain.knowledge.parser import parse_docx, parse_md, parse_pdf, parse_txt
from app.repositories.knowledge_repo import KnowledgeRepository

logger = structlog.get_logger()

_PARSERS = {
    "txt": parse_txt,
    "md": parse_md,
    "pdf": parse_pdf,
    "docx": parse_docx,
}


async def parse_document(doc_id: str) -> None:
    """Parse a single document: read file → chunk → save chunks → update status."""
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        repo = KnowledgeRepository(session)
        doc = await repo.get_document(doc_id)
        if doc is None:
            logger.error("doc_not_found", doc_id=doc_id)
            return

        parser = _PARSERS.get(doc.file_type)
        if parser is None:
            await repo.update_document_status(
                doc.id, status="failed", error=f"no parser for type {doc.file_type}"
            )
            return

        try:
            text = parser(doc.file_path)
        except DocumentParseError as e:
            logger.warning("parse_failed", doc_id=doc.id, error=str(e))
            await repo.update_document_status(doc.id, status="failed", error=str(e))
            return
        except Exception as e:  # noqa: BLE001
            logger.exception("parse_unexpected", doc_id=doc.id)
            await repo.update_document_status(
                doc.id, status="failed", error=f"{type(e).__name__}: {e}"
            )
            return

        chunks_raw = chunk_text(
            text,
            min_length=settings.chunk_min_length,
            max_length=settings.chunk_max_length,
        )
        chunks = [
            {
                "chunk_index": idx,
                "content": c,
                "content_length": len(c),
            }
            for idx, c in enumerate(chunks_raw)
        ]

        await repo.add_chunks(doc_id=doc.id, kb_id=doc.kb_id, chunks=chunks)
        await repo.update_document_status(
            doc.id, status="success", chunk_count=len(chunks)
        )

        # v0.5 — incremental sync: push new chunks to ChromaDB (spec §7)
        # 关键:bge embeddings 必须由调用方预计算后传入,否则 ChromaDB 会用默认英文
        # embedding function,导致语义检索错乱(R1 修复)。
        try:
            from app.domain.knowledge.vector_index import VectorIndex
            from app.services.embedding import EmbeddingService
            new_chunks = await repo.list_chunks_for_doc(doc.id)
            if new_chunks:
                texts = [c.content for c in new_chunks]
                embeddings = EmbeddingService.embed(texts)
                index = VectorIndex(doc.kb_id)
                index.add_chunks(
                    [
                        {
                            "id": c.id,
                            "content": c.content,
                            "doc_id": c.doc_id,
                            "chunk_index": c.chunk_index,
                        }
                        for c in new_chunks
                    ],
                    embeddings=embeddings,
                )
                logger.info("v0.5_chroma_indexed", doc_id=doc.id, chunks=len(new_chunks))
        except Exception as e:  # noqa: BLE001
            # 只把本批 new_chunks 标记 pending(不是整个 doc 的全部 chunks),
            # 避免重解析时污染已成功索引的旧 chunks(R5 修复)。
            try:
                await repo.mark_chunks_pending([c.id for c in new_chunks])
            except Exception:
                pass
            logger.warning(
                "v0.5_chroma_index_failed",
                doc_id=doc.id, error=str(e), will_retry_on_restart=True,
            )

        logger.info("parse_done", doc_id=doc.id, chunks=len(chunks))


def schedule_parse(doc_id: str) -> asyncio.Task[None]:
    """Fire-and-forget background execution. Returns the asyncio.Task."""
    return asyncio.create_task(parse_document(doc_id))

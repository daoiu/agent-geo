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
        logger.info("parse_done", doc_id=doc.id, chunks=len(chunks))


def schedule_parse(doc_id: str) -> asyncio.Task[None]:
    """Fire-and-forget background execution. Returns the asyncio.Task."""
    return asyncio.create_task(parse_document(doc_id))

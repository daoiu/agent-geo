"""Knowledge base API: CRUD, document listing, keyword search."""
from __future__ import annotations

import uuid
from pathlib import Path

import jieba  # noqa: F401  # re-exported via retriever.extract_search_keywords
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.core.config import get_settings
from app.domain.knowledge.retriever import extract_search_keywords
from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSearchResult,
)
from app.models.orm_v02 import (
    KnowledgeDocumentORM,
    TaskORM,
)
from app.repositories.knowledge_repo import KnowledgeRepository
from app.tasks.parser_worker import schedule_parse

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

_ALLOWED_EXTENSIONS = {"pdf", "docx", "md", "txt"}


@router.post("", status_code=201, response_model=KnowledgeBase)
async def create_kb(
    body: KnowledgeBaseCreate,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeBaseORM:
    repo = KnowledgeRepository(session)
    return await repo.create_kb(name=body.name, description=body.description)


@router.get("", response_model=list[KnowledgeBase])
async def list_kbs(
    session: AsyncSession = Depends(get_session),
) -> list[KnowledgeBaseORM]:
    repo = KnowledgeRepository(session)
    return await repo.list_kbs()


@router.get("/{kb_id}")
async def get_kb(
    kb_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """KB details + documents list."""
    repo = KnowledgeRepository(session)
    kb = await repo.get_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    docs = await repo.list_documents(kb_id)
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "created_at": kb.created_at.isoformat(),
        "documents": [KnowledgeDocument.model_validate(d) for d in docs],
    }


@router.delete("/{kb_id}", status_code=204, response_class=Response)
async def delete_kb(
    kb_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Delete KB. Returns 409 if any task references it."""
    result = await session.execute(
        select(TaskORM).where(TaskORM.kb_id == kb_id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="knowledge base has associated tasks; delete or cancel them first",
        )
    repo = KnowledgeRepository(session)
    kb = await repo.get_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")
    await repo.delete_kb(kb_id)
    return Response(status_code=204)


@router.delete("/{kb_id}/documents/{doc_id}", status_code=204, response_class=Response)
async def delete_document(
    kb_id: str,
    doc_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    repo = KnowledgeRepository(session)
    doc = await repo.get_document(doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="document not found")
    await session.execute(
        delete(KnowledgeDocumentORM).where(KnowledgeDocumentORM.id == doc_id)
    )
    await session.commit()
    return Response(status_code=204)


@router.get("/{kb_id}/chunks", response_model=KnowledgeSearchResult)
async def search_chunks(
    kb_id: str,
    q: str,
    limit: int = 5,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeSearchResult:
    """Keyword-based chunk search using jieba segmentation."""
    repo = KnowledgeRepository(session)
    kb = await repo.get_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")

    # jieba: extract keywords via shared helper (same logic as task worker)
    keywords = extract_search_keywords(q)
    chunks = await repo.search_chunks_by_keyword(
        kb_id=kb_id, keywords=keywords, top_k=limit
    )
    return KnowledgeSearchResult(
        query=q,
        chunks=[KnowledgeChunk.model_validate(c) for c in chunks],
    )


@router.post("/{kb_id}/documents", status_code=201, response_model=KnowledgeDocument)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeDocumentORM:
    """Upload a document to a knowledge base. Triggers async parsing."""
    settings = get_settings()
    repo = KnowledgeRepository(session)
    kb = await repo.get_kb(kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")

    # Validate type
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")
    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported file type: .{ext}; allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )

    # Save to disk
    doc_id = str(uuid.uuid4())
    upload_dir = (
        Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / kb_id
    )
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{doc_id}.{ext}"

    # Stream with size check
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    written = 0
    with file_path.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                out.close()
                file_path.unlink(missing_ok=True)
                # Spec §6.1 + 验收清单场景 3 要求 422
                raise HTTPException(
                    status_code=422,
                    detail=f"file too large; max {settings.max_upload_size_mb}MB",
                )
            out.write(chunk)

    # Create DB record
    doc = await repo.add_document(
        kb_id=kb_id,
        filename=file.filename,
        file_path=str(file_path),
        file_type=ext,
        file_size=written,
    )

    # Schedule parser worker
    schedule_parse(doc.id)

    return doc

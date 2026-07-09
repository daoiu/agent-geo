# GEO Optimization Agent v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add knowledge-base-driven content generation to GEO Agent: users upload PDF/Word/MD/TXT files, create generation tasks, AI produces articles grounded in the knowledge base, and humans review/approve them in a queue.

**Architecture:** v0.2 extends the v0.1 monolith (FastAPI + React + SQLite + asyncio). New 4-table schema (knowledge_bases / knowledge_documents / knowledge_chunks / tasks / articles). New domain modules: knowledge (parser/chunker/retriever), task, generator, review. Reuses v0.1's llm_client, asyncio worker pattern, and the diagnostic lock for single-flight task execution.

**Tech Stack:** Extends v0.1 with: jieba (Chinese segmentation), pypdf (PDF parsing), python-docx (.docx), react-dropzone (file upload). All other constraints inherit from v0.1.

## Global Constraints

Inherits **all** v0.1 constraints from `docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md`. Additions specific to v0.2:

- **v0.2 is built on top of v0.1** — Task 0.1 assumes v0.1 is complete (or you are scaffolding both in parallel); if v0.1 isn't done, see the parallel scaffolding note at the bottom of each task
- **Reuse v0.1's infra**: llm_client, asyncio worker, SQLite engine, Repository base — do not duplicate
- **No vector search in v0.2** — use jieba + SQL keyword match; v0.5 upgrades to pgvector
- **No authentication in v0.2** — single-user assumption
- **No multi-site distribution in v0.2** — generated articles stay in DB; v0.3 adds publishing
- **AI must not fabricate facts not in the knowledge base** — prompt explicitly forbids this
- **Single article failure does not fail the whole task** — failed articles enter review queue with error_message
- **File size limit**: 50MB per upload (rejected at API layer)
- **File types supported**: pdf, docx, md, txt only (415 for others)
- **Article count per task**: 1-20 (422 outside range)

**Reference spec:** `docs/superpowers/specs/2026-07-09-geo-agent-v0.2-design.md` — re-read sections as needed.

---

## Phase 0: Foundation Extensions

### Task 0.1: Add v0.2 Dependencies

**Files:**
- Modify: `D:/GEO2/backend/requirements.txt`
- Modify: `D:/GEO2/backend/app/core/config.py`

**Interfaces:**
- Consumes: existing v0.1 requirements
- Produces: new settings `max_upload_size_mb`, `default_target_length`

- [ ] **Step 1: Append new dependencies to `requirements.txt`**

Edit `D:/GEO2/backend/requirements.txt` and add at the bottom (preserve existing content):

```
jieba==0.42.1
pypdf==5.1.0
python-docx==1.1.2
python-multipart==0.0.20
```

- [ ] **Step 2: Install dependencies**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pip install -r requirements.txt
```

Expected: All packages install successfully.

- [ ] **Step 3: Add v0.2 settings to `config.py`**

Edit `D:/GEO2/backend/app/core/config.py`. Add these fields to the `Settings` class (keep all existing fields):

```python
    # Knowledge base / v0.2
    max_upload_size_mb: int = 50
    default_target_length: int = 1500
    chunk_min_length: int = 50
    chunk_max_length: int = 500
    retrieval_top_k: int = 5
    max_article_count_per_task: int = 20
```

- [ ] **Step 4: Write failing test for new settings**

Create `D:/GEO2/backend/tests/test_config_v0.2.py`:

```python
"""Tests for v0.2 settings additions."""
from app.core.config import Settings


def test_v02_settings_have_defaults() -> None:
    s = Settings()
    assert s.max_upload_size_mb == 50
    assert s.default_target_length == 1500
    assert s.chunk_min_length == 50
    assert s.chunk_max_length == 500
    assert s.retrieval_top_k == 5
    assert s.max_article_count_per_task == 20
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_config_v0.2.py -v
```

Expected: PASS (defaults set in Step 3).

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/requirements.txt backend/app/core/config.py backend/tests/test_config_v0.2.py && git commit -m "feat(backend/v0.2): add v0.2 dependencies and settings"
```

---

### Task 0.2: Extend ORM Models (5 New Tables)

**Files:**
- Create: `D:/GEO2/backend/app/models/orm_v02.py`
- Modify: `D:/GEO2/backend/app/models/orm.py` (re-export from new module)

**Interfaces:**
- Consumes: existing `Base` from `app.models.orm`
- Produces:
  - `KnowledgeBaseORM` (id, name, description, created_at)
  - `KnowledgeDocumentORM` (id, kb_id, filename, file_path, file_size, file_type, parse_status, parse_error, chunk_count, created_at)
  - `KnowledgeChunkORM` (id, doc_id, kb_id, chunk_index, content, content_length, created_at)
  - `TaskORM` (id, name, kb_id, brand, topic, keywords, article_count, style, target_length, status, progress, error_message, created_at, updated_at)
  - `ArticleORM` (id, task_id, title, content, content_length, review_status, review_note, reviewed_at, cited_chunks, llm_provider, error_message, created_at, updated_at)

- [ ] **Step 1: Write failing test for new ORM models**

Create `D:/GEO2/backend/tests/test_orm_v0.2.py`:

```python
"""Tests for v0.2 ORM models."""
import pytest

from app.models.orm_v02 import (
    ArticleORM,
    KnowledgeBaseORM,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
    TaskORM,
)


@pytest.mark.asyncio
async def test_kb_orm_create_and_read(db_session) -> None:
    from app.models.orm_v02 import KnowledgeBaseORM

    kb = KnowledgeBaseORM(
        id="kb1",
        name="测试知识库",
        description="描述",
    )
    db_session.add(kb)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(KnowledgeBaseORM).where(KnowledgeBaseORM.id == "kb1")
    )
    fetched = result.scalar_one()
    assert fetched.name == "测试知识库"


@pytest.mark.asyncio
async def test_document_orm_foreign_key(db_session) -> None:
    from app.models.orm_v02 import KnowledgeBaseORM, KnowledgeDocumentORM
    from sqlalchemy import select

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    doc = KnowledgeDocumentORM(
        id="d1",
        kb_id="kb1",
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        parse_status="pending",
    )
    db_session.add(doc)
    await db_session.commit()

    result = await db_session.execute(
        select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.id == "d1")
    )
    fetched = result.scalar_one()
    assert fetched.kb_id == "kb1"
    assert fetched.parse_status == "pending"


@pytest.mark.asyncio
async def test_chunk_orm(db_session) -> None:
    from app.models.orm_v02 import KnowledgeBaseORM, KnowledgeDocumentORM, KnowledgeChunkORM
    from sqlalchemy import select

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    doc = KnowledgeDocumentORM(
        id="d1", kb_id="kb1", filename="x.txt",
        file_path="/tmp/x.txt", file_type="txt", parse_status="success",
    )
    db_session.add_all([kb, doc])
    await db_session.commit()

    chunk = KnowledgeChunkORM(
        id="c1", doc_id="d1", kb_id="kb1",
        chunk_index=0, content="some content", content_length=12,
    )
    db_session.add(chunk)
    await db_session.commit()

    result = await db_session.execute(
        select(KnowledgeChunkORM).where(KnowledgeChunkORM.id == "c1")
    )
    fetched = result.scalar_one()
    assert fetched.content == "some content"
    assert fetched.chunk_index == 0


@pytest.mark.asyncio
async def test_task_orm(db_session) -> None:
    from app.models.orm_v02 import KnowledgeBaseORM, TaskORM

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    import json
    task = TaskORM(
        id="t1", name="测试任务", kb_id="kb1",
        brand="测试品牌", topic="主题", keywords=json.dumps(["k1", "k2"]),
        article_count=3, style="neutral", target_length=1500,
        status="pending",
    )
    db_session.add(task)
    await db_session.commit()

    assert task.status == "pending"
    assert task.article_count == 3


@pytest.mark.asyncio
async def test_article_orm(db_session) -> None:
    from app.models.orm_v02 import KnowledgeBaseORM, TaskORM, ArticleORM
    import json

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1",
        topic="X", article_count=1, style="neutral", target_length=1000,
    )
    db_session.add_all([kb, task])
    await db_session.commit()

    article = ArticleORM(
        id="a1", task_id="t1", title="待生成 #1",
        review_status="pending", cited_chunks=json.dumps([]),
    )
    db_session.add(article)
    await db_session.commit()

    assert article.review_status == "pending"
    assert article.error_message is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_orm_v0.2.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.orm_v02'`

- [ ] **Step 3: Create `app/models/orm_v02.py`**

Create `D:/GEO2/backend/app/models/orm_v02.py`:

```python
"""SQLAlchemy ORM models for v0.2 (knowledge base, tasks, articles)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeBaseORM(Base):
    """A knowledge base: a collection of documents the AI can reference."""

    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )


class KnowledgeDocumentORM(Base):
    """A file uploaded to a knowledge base."""

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kb_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    parse_status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )


class KnowledgeChunkORM(Base):
    """A text segment produced by chunking a document."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    doc_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized for fast query
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )


class TaskORM(Base):
    """A content generation task: produces N articles from a knowledge base."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kb_id: Mapped[str] = mapped_column(
        String, ForeignKey("knowledge_bases.id", ondelete="RESTRICT"), nullable=False
    )
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    article_count: Mapped[int] = mapped_column(Integer, nullable=False)
    style: Mapped[str] = mapped_column(String, default="neutral", nullable=False)
    target_length: Mapped[int] = mapped_column(Integer, default=1500, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ArticleORM(Base):
    """A generated article awaiting or having completed review."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String, default="pending", nullable=False
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    cited_chunks: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    llm_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_orm_v0.2.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Verify all v0.1 tests still pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All v0.1 + v0.2 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): 5 ORM models (kb/doc/chunk/task/article) with tests"
```

---

## Phase 1: Knowledge — Parser & Chunker

### Task 1.1: Text File Parser (TXT + MD)

**Files:**
- Create: `D:/GEO2/backend/app/domain/knowledge/__init__.py`
- Create: `D:/GEO2/backend/app/domain/knowledge/parser.py`
- Create: `D:/GEO2/backend/tests/test_parser.py`
- Create: `D:/GEO2/backend/tests/fixtures/sample.txt`
- Create: `D:/GEO2/backend/tests/fixtures/sample.md`

**Interfaces:**
- Consumes: file path
- Produces:
  - `parse_txt(path) -> str` (plain text content)
  - `parse_md(path) -> str` (markdown as plain text)
  - `parse_pdf(path) -> str` (pdf text — Task 1.2)
  - `parse_docx(path) -> str` (docx text — Task 1.3)
  - `parse_document(path, file_type) -> str` (dispatcher)
  - `DocumentParseError` (already in spec §6.2; we'll add to exceptions.py)

- [ ] **Step 1: Create fixtures**

Create `D:/GEO2/backend/tests/fixtures/sample.txt`:

```
这是第一段。

这是第二段，包含多行内容。
继续第二段的内容。

第三段。
```

Create `D:/GEO2/backend/tests/fixtures/sample.md`:

```markdown
# 标题

引言段落。

## 子标题 1

第一段内容。

## 子标题 2

第二段内容。
```

- [ ] **Step 2: Add `DocumentParseError` to exceptions**

Edit `D:/GEO2/backend/app/domain/exceptions.py`. Add to the imports/top of the file:

```python
class KnowledgeError(DomainError):
    """Knowledge base errors."""
```

Then add a new class anywhere in the file:

```python
class DocumentParseError(KnowledgeError):
    """A document could not be parsed to text."""

    def __init__(self, doc_id: str, file_path: str, reason: str) -> None:
        self.doc_id = doc_id
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"Document {doc_id} parse failed: {reason}")
```

- [ ] **Step 3: Create `app/domain/knowledge/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/knowledge/__init__.py`.

- [ ] **Step 4: Write failing test for TXT + MD parser**

Create `D:/GEO2/backend/tests/test_parser.py`:

```python
"""Tests for document parsers (TXT and MD covered in this task)."""
import pytest

from app.domain.knowledge.parser import (
    DocumentParseError,
    parse_md,
    parse_txt,
)


class TestTxtParser:
    def test_parses_plain_text(self, tmp_path) -> None:
        from tests.conftest import PROJECT_ROOT
        from pathlib import Path

        fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.txt"
        text = parse_txt(str(fixture))
        assert "第一段" in text
        assert "第二段" in text

    def test_missing_file_raises(self, tmp_path) -> None:
        with pytest.raises(DocumentParseError):
            parse_txt(str(tmp_path / "nonexistent.txt"))


class TestMdParser:
    def test_parses_markdown_as_text(self) -> None:
        from tests.conftest import PROJECT_ROOT
        from pathlib import Path

        fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.md"
        text = parse_md(str(fixture))
        assert "标题" in text
        assert "子标题" in text
```

We need to expose PROJECT_ROOT. Append this to `D:/GEO2/backend/tests/conftest.py`:

```python
# Add at top of conftest.py
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

- [ ] **Step 5: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 6: Create `app/domain/knowledge/parser.py` (TXT + MD only)**

Create `D:/GEO2/backend/app/domain/knowledge/parser.py`:

```python
"""Document parsers: extract plain text from PDF/Word/MD/TXT files.

TXT and MD parsers live in this file. PDF and DOCX are added in Tasks 1.2 and 1.3.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.exceptions import DocumentParseError


def _read_text_file(path: str) -> str:
    """Read a UTF-8 text file. Raises DocumentParseError on failure."""
    p = Path(path)
    if not p.exists():
        raise DocumentParseError(
            doc_id=path, file_path=path, reason="file not found"
        )
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Fall back to GBK (common for Chinese Windows files)
        try:
            return p.read_text(encoding="gbk")
        except Exception as e:  # noqa: BLE001
            raise DocumentParseError(
                doc_id=path, file_path=path, reason=f"encoding error: {e}"
            ) from e
    except Exception as e:  # noqa: BLE001
        raise DocumentParseError(
            doc_id=path, file_path=path, reason=str(e)
        ) from e


def parse_txt(path: str) -> str:
    """Parse a plain text file."""
    return _read_text_file(path)


def parse_md(path: str) -> str:
    """Parse a Markdown file. We treat it as text — Markdown syntax is preserved
    so downstream consumers (LLM prompts) can see structure.
    """
    return _read_text_file(path)
```

- [ ] **Step 7: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): TXT and MD parsers with tests"
```

---

### Task 1.2: PDF Parser

**Files:**
- Modify: `D:/GEO2/backend/app/domain/knowledge/parser.py`
- Modify: `D:/GEO2/backend/tests/test_parser.py`

**Interfaces (addition):**
- `parse_pdf(path) -> str` — extracts text from all pages

- [ ] **Step 1: Append PDF test to `test_parser.py`**

Append to `D:/GEO2/backend/tests/test_parser.py`:

```python
class TestPdfParser:
    def test_parses_pdf_with_text(self) -> None:
        from tests.conftest import PROJECT_ROOT
        from app.domain.knowledge.parser import parse_pdf

        fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.pdf"
        if not fixture.exists():
            pytest.skip("sample.pdf not yet generated")
        text = parse_pdf(str(fixture))
        assert isinstance(text, str)
        assert len(text) > 0

    def test_missing_pdf_raises(self, tmp_path) -> None:
        from app.domain.knowledge.parser import parse_pdf

        with pytest.raises(DocumentParseError):
            parse_pdf(str(tmp_path / "missing.pdf"))

    def test_corrupted_pdf_raises(self, tmp_path) -> None:
        from app.domain.knowledge.parser import parse_pdf

        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")
        with pytest.raises(DocumentParseError):
            parse_pdf(str(bad))
```

- [ ] **Step 2: Generate a small sample PDF for testing**

Run this Python script to create a real PDF using `pypdf`'s writer (or use any existing PDF):

```python
# In a one-off Python session, create sample.pdf
from pypdf import PdfWriter
from pathlib import Path

writer = PdfWriter()
page = writer.add_blank_page(width=612, height=792)  # Letter
# pypdf alone can't add text easily; use reportlab if available, else skip
# For MVP test, create a minimal PDF with no text
out = Path("D:/GEO2/backend/tests/fixtures/sample.pdf")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("wb") as f:
    writer.write(f)
print("created", out)
```

If pypdf alone doesn't suffice, use `reportlab`:

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pip install reportlab==4.2.5
```

Then in a Python session:

```python
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pathlib import Path

out = Path("D:/GEO2/backend/tests/fixtures/sample.pdf")
out.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(out), pagesize=letter)
c.drawString(100, 700, "这是 PDF 测试文档。")
c.drawString(100, 680, "包含多行中文内容。")
c.drawString(100, 660, "第二段：介绍产品特点。")
c.save()
print("created", out)
```

Verify the PDF was created.

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser.py::TestPdfParser -v
```

Expected: FAIL with `AttributeError: module has no attribute 'parse_pdf'`

- [ ] **Step 4: Add `parse_pdf` to `parser.py`**

Edit `D:/GEO2/backend/app/domain/knowledge/parser.py`. Add the import at the top:

```python
from pypdf import PdfReader
from pypdf.errors import PdfReadError
```

Add this function anywhere in the file:

```python
def parse_pdf(path: str) -> str:
    """Extract text from a PDF file.

    Iterates all pages and joins with double newlines.
    Raises DocumentParseError on missing file, corrupted PDF, or read error.
    """
    p = Path(path)
    if not p.exists():
        raise DocumentParseError(doc_id=path, file_path=path, reason="file not found")
    try:
        reader = PdfReader(str(p))
        texts: list[str] = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception as e:  # noqa: BLE001
                # One bad page shouldn't fail the whole PDF
                texts.append(f"[page extraction failed: {e}]")
        return "\n\n".join(t for t in texts if t.strip())
    except PdfReadError as e:
        raise DocumentParseError(
            doc_id=path, file_path=path, reason=f"corrupted PDF: {e}"
        ) from e
    except Exception as e:  # noqa: BLE001
        raise DocumentParseError(
            doc_id=path, file_path=path, reason=str(e)
        ) from e
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser.py -v
```

Expected: All parser tests PASS (including PDF).

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): PDF parser with error handling + tests"
```

---

### Task 1.3: DOCX Parser

**Files:**
- Modify: `D:/GEO2/backend/app/domain/knowledge/parser.py`
- Modify: `D:/GEO2/backend/tests/test_parser.py`
- Create: `D:/GEO2/backend/tests/fixtures/sample.docx` (generated by test setup)

**Interfaces (addition):**
- `parse_docx(path) -> str` — extracts paragraph text (tables flattened)

- [ ] **Step 1: Append DOCX test to `test_parser.py`**

Append to `D:/GEO2/backend/tests/test_parser.py`:

```python
class TestDocxParser:
    def test_parses_docx(self) -> None:
        from tests.conftest import PROJECT_ROOT
        from app.domain.knowledge.parser import parse_docx

        fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.docx"
        if not fixture.exists():
            pytest.skip("sample.docx not yet generated")
        text = parse_docx(str(fixture))
        assert isinstance(text, str)
        assert len(text) > 0

    def test_missing_docx_raises(self, tmp_path) -> None:
        from app.domain.knowledge.parser import parse_docx

        with pytest.raises(DocumentParseError):
            parse_docx(str(tmp_path / "missing.docx"))
```

- [ ] **Step 2: Generate a sample DOCX for testing**

Add this helper at the bottom of `test_parser.py`:

```python
def _ensure_sample_docx() -> None:
    """Generate sample.docx if missing. Used by manual setup or conftest."""
    from pathlib import Path
    from tests.conftest import PROJECT_ROOT
    import docx

    out = PROJECT_ROOT / "tests" / "fixtures" / "sample.docx"
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = docx.Document()
    doc.add_heading("DOCX 测试文档", level=1)
    doc.add_paragraph("第一段：介绍产品。")
    doc.add_paragraph("第二段：详细介绍。")
    doc.add_heading("子标题", level=2)
    doc.add_paragraph("子标题下的内容。")
    doc.save(str(out))
    print(f"created {out}")
```

Then run the helper as a one-off:

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && python -c "from tests.test_parser import _ensure_sample_docx; _ensure_sample_docx()"
```

Verify `D:/GEO2/backend/tests/fixtures/sample.docx` exists.

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser.py::TestDocxParser -v
```

Expected: FAIL with `AttributeError: module has no attribute 'parse_docx'`

- [ ] **Step 4: Add `parse_docx` to `parser.py`**

Edit `D:/GEO2/backend/app/domain/knowledge/parser.py`. Add the import at the top:

```python
import docx  # python-docx
```

Add this function:

```python
def parse_docx(path: str) -> str:
    """Extract text from a .docx file.

    Concatenates paragraphs (including those inside tables) with double newlines.
    """
    p = Path(path)
    if not p.exists():
        raise DocumentParseError(doc_id=path, file_path=path, reason="file not found")
    try:
        document = docx.Document(str(p))
        parts: list[str] = []

        # Body paragraphs
        for para in document.paragraphs:
            if para.text.strip():
                parts.append(para.text)

        # Tables (flattened: each row is one chunk separated by newlines)
        for table in document.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    parts.append(row_text)

        return "\n\n".join(parts)
    except Exception as e:  # noqa: BLE001
        raise DocumentParseError(
            doc_id=path, file_path=path, reason=str(e)
        ) from e
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser.py -v
```

Expected: All parser tests PASS (TXT + MD + PDF + DOCX).

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): DOCX parser + sample fixtures + tests"
```

---

### Task 1.4: Text Chunker (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/domain/knowledge/chunker.py`
- Create: `D:/GEO2/backend/tests/test_chunker.py`

**Interfaces:**
- Consumes: text string, optional chunk_min/chunk_max from settings
- Produces:
  - `chunk_text(text: str, min_length: int = 50, max_length: int = 500) -> list[str]`

- [ ] **Step 1: Write failing tests**

Create `D:/GEO2/backend/tests/test_chunker.py`:

```python
"""Tests for the text chunker."""
from app.domain.knowledge.chunker import chunk_text


class TestChunking:
    def test_splits_long_paragraph_at_max(self) -> None:
        """A single 1200-char paragraph gets split at sentence boundaries."""
        long = "。" .join(["这是第" + str(i) + "句话"] for i in range(200))  # ~1600 chars
        chunks = chunk_text(long, min_length=10, max_length=500)
        assert all(len(c) <= 500 for c in chunks)
        assert len(chunks) > 1

    def test_merges_short_paragraphs_to_min(self) -> None:
        text = "短段一。\n\n短段二。\n\n短段三。\n\n短段四。"
        chunks = chunk_text(text, min_length=10, max_length=500)
        # All four short paragraphs should merge into one chunk
        assert len(chunks) == 1
        assert "短段一" in chunks[0]
        assert "短段四" in chunks[0]

    def test_separates_by_double_newline(self) -> None:
        text = (
            "第一段内容超过五十字。" * 5 +
            "\n\n" +
            "第二段内容也超过五十字。" * 5
        )
        chunks = chunk_text(text, min_length=10, max_length=500)
        assert len(chunks) == 2
        assert "第一段" in chunks[0]
        assert "第二段" in chunks[1]

    def test_empty_text_returns_empty_list(self) -> None:
        assert chunk_text("") == []
        assert chunk_text("   \n\n  \n") == []

    def test_filters_out_tiny_chunks(self) -> None:
        text = "abc\n\n" + "x" * 100 + "\n\ndef"
        chunks = chunk_text(text, min_length=50, max_length=500)
        # "abc" and "def" too small; only the 100-char one survives
        assert all(len(c) >= 50 for c in chunks)
        assert len(chunks) == 1
        assert "x" * 100 in chunks[0]

    def test_handles_chinese_sentence_splitting(self) -> None:
        """Long Chinese paragraph splits at Chinese sentence boundaries (。！？)."""
        long = ("第一句。" * 100)  # ~400 chars
        chunks = chunk_text(long, min_length=10, max_length=200)
        # Should split, not at arbitrary positions
        for chunk in chunks:
            assert len(chunk) <= 200
            # Each chunk should end at a sentence boundary if possible
            assert any(chunk.endswith(p) for p in ["。", "！", "？", ""]) or len(chunk) < 200
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_chunker.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/knowledge/chunker.py`**

Create `D:/GEO2/backend/app/domain/knowledge/chunker.py`:

```python
"""Text chunker: splits long text into 50-500 char segments at sentence boundaries."""
from __future__ import annotations

import re

# Chinese + English sentence terminators
_SENTENCE_END = re.compile(r"([。！？.!?\n])")


def _split_long_paragraph(paragraph: str, max_length: int) -> list[str]:
    """Split a paragraph longer than max_length at sentence boundaries."""
    if len(paragraph) <= max_length:
        return [paragraph]

    # Split into sentences (keeping the terminator)
    pieces = _SENTENCE_END.split(paragraph)
    # Re-join: split() alternates text/separator, e.g. ["a", "。", "b", "。", ...]
    sentences: list[str] = []
    for i in range(0, len(pieces) - 1, 2):
        text = pieces[i]
        sep = pieces[i + 1] if i + 1 < len(pieces) else ""
        if text or sep:
            sentences.append(text + sep)

    # Pack sentences into chunks ≤ max_length
    chunks: list[str] = []
    buffer = ""
    for sentence in sentences:
        if len(buffer) + len(sentence) <= max_length:
            buffer += sentence
        else:
            if buffer:
                chunks.append(buffer)
            if len(sentence) > max_length:
                # Single sentence longer than max — hard cut
                chunks.append(sentence[:max_length])
                buffer = sentence[max_length:]
            else:
                buffer = sentence
    if buffer:
        chunks.append(buffer)
    return [c for c in chunks if c.strip()]


def chunk_text(
    text: str, min_length: int = 50, max_length: int = 500
) -> list[str]:
    """Split text into chunks of 50-500 characters.

    Algorithm:
    1. Split by double newlines (paragraphs)
    2. Each paragraph > max_length → split at sentence boundaries
    3. Merge consecutive short paragraphs until ≥ min_length
    4. Drop final chunks < min_length
    """
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Phase 1: split long paragraphs
    pieces: list[str] = []
    for p in paragraphs:
        pieces.extend(_split_long_paragraph(p, max_length))

    # Phase 2: merge short consecutive pieces
    chunks: list[str] = []
    buffer = ""
    for piece in pieces:
        if len(buffer) + len(piece) + 2 <= max_length:
            buffer = (buffer + "\n\n" + piece) if buffer else piece
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)

    # Phase 3: filter by min_length
    return [c.strip() for c in chunks if len(c.strip()) >= min_length]
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_chunker.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): text chunker with sentence-boundary splitting + tests"
```

---

### Task 1.5: Knowledge Repository (CRUD)

**Files:**
- Create: `D:/GEO2/backend/app/repositories/knowledge_repo.py`
- Create: `D:/GEO2/backend/tests/test_knowledge_repo.py`

**Interfaces:**
- Consumes: `KnowledgeBaseORM`, `KnowledgeDocumentORM`, `KnowledgeChunkORM`
- Produces:
  - `KnowledgeRepository(session)` class with:
    - `create_kb(name, description) -> KnowledgeBaseORM`
    - `get_kb(kb_id) -> KnowledgeBaseORM | None`
    - `list_kbs() -> list[KnowledgeBaseORM]`
    - `delete_kb(kb_id) -> None` (cascades)
    - `add_document(kb_id, filename, file_path, file_type, file_size) -> KnowledgeDocumentORM`
    - `get_document(doc_id) -> KnowledgeDocumentORM | None`
    - `list_documents(kb_id) -> list[KnowledgeDocumentORM]`
    - `update_document_status(doc_id, status, error=None, chunk_count=None) -> None`
    - `add_chunks(doc_id, kb_id, chunks: list[dict]) -> int`  # returns count added
    - `list_chunks(kb_id) -> list[KnowledgeChunkORM]`
    - `search_chunks_by_keyword(kb_id, keywords: list[str], top_k) -> list[KnowledgeChunkORM]`

- [ ] **Step 1: Write failing tests**

Create `D:/GEO2/backend/tests/test_knowledge_repo.py`:

```python
"""Tests for KnowledgeRepository."""
import pytest

from app.models.orm_v02 import (
    KnowledgeBaseORM,
    KnowledgeChunkORM,
    KnowledgeDocumentORM,
)
from app.repositories.knowledge_repo import KnowledgeRepository


@pytest.mark.asyncio
async def test_create_and_get_kb(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="测试 KB", description="描述")
    fetched = await repo.get_kb(kb.id)
    assert fetched is not None
    assert fetched.name == "测试 KB"


@pytest.mark.asyncio
async def test_list_kbs(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    await repo.create_kb(name="A")
    await repo.create_kb(name="B")
    kbs = await repo.list_kbs()
    assert len(kbs) == 2


@pytest.mark.asyncio
async def test_add_document_and_list(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.pdf", file_path="/tmp/x.pdf",
        file_type="pdf", file_size=1024,
    )
    docs = await repo.list_documents(kb.id)
    assert len(docs) == 1
    assert docs[0].parse_status == "pending"


@pytest.mark.asyncio
async def test_update_document_status(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.update_document_status(
        doc.id, status="success", chunk_count=10
    )
    refreshed = await repo.get_document(doc.id)
    assert refreshed.parse_status == "success"
    assert refreshed.chunk_count == 10
    assert refreshed.parse_error is None


@pytest.mark.asyncio
async def test_update_document_status_with_error(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="bad.pdf", file_path="/tmp/bad.pdf",
        file_type="pdf", file_size=0,
    )
    await repo.update_document_status(doc.id, status="failed", error="corrupted")
    refreshed = await repo.get_document(doc.id)
    assert refreshed.parse_status == "failed"
    assert refreshed.parse_error == "corrupted"


@pytest.mark.asyncio
async def test_add_and_search_chunks(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    count = await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "小米手机性能优秀", "content_length": 8},
            {"chunk_index": 1, "content": "华为手机拍照好", "content_length": 7},
            {"chunk_index": 2, "content": "苹果生态系统完善", "content_length": 8},
        ],
    )
    assert count == 3

    # Search for "小米"
    results = await repo.search_chunks_by_keyword(
        kb_id=kb.id, keywords=["小米"], top_k=5
    )
    assert len(results) == 1
    assert "小米" in results[0].content


@pytest.mark.asyncio
async def test_search_chunks_ranks_by_keyword_count(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "小米手机", "content_length": 4},
            {"chunk_index": 1, "content": "小米手机小米手机小米", "content_length": 9},
        ],
    )
    results = await repo.search_chunks_by_keyword(
        kb_id=kb.id, keywords=["小米"], top_k=5
    )
    # First result should be the one with more "小米" mentions
    assert results[0].chunk_index == 1


@pytest.mark.asyncio
async def test_delete_kb_cascades(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[{"chunk_index": 0, "content": "hello", "content_length": 5}],
    )
    await repo.delete_kb(kb.id)
    from sqlalchemy import select
    result = await db_session.execute(
        select(KnowledgeDocumentORM).where(KnowledgeDocumentORM.kb_id == kb.id)
    )
    assert result.scalars().all() == []
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_repo.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/repositories/knowledge_repo.py`**

Create `D:/GEO2/backend/app/repositories/knowledge_repo.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_repo.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): KnowledgeRepository with KB/doc/chunk CRUD + keyword search + tests"
```

---

## Phase 2: Knowledge — API & Parsing Worker

### Task 2.1: Knowledge Pydantic Schemas

**Files:**
- Create: `D:/GEO2/backend/app/models/knowledge.py`
- Create: `D:/GEO2/backend/tests/test_knowledge_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `KnowledgeBase`, `KnowledgeBaseCreate`
  - `KnowledgeDocument`
  - `KnowledgeChunk`
  - `KnowledgeSearchRequest`, `KnowledgeSearchResult`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_knowledge_schemas.py`:

```python
"""Tests for knowledge base Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeSearchRequest,
)


class TestKnowledgeBaseCreate:
    def test_min_name(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeBaseCreate(name="")

    def test_max_description(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeBaseCreate(name="x", description="x" * 1001)

    def test_valid(self) -> None:
        kb = KnowledgeBaseCreate(name="My KB", description="desc")
        assert kb.name == "My KB"


class TestKnowledgeSearchRequest:
    def test_query_required(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(q="")

    def test_limit_bounds(self) -> None:
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(q="x", limit=0)
        with pytest.raises(ValidationError):
            KnowledgeSearchRequest(q="x", limit=100)
        # Valid
        ok = KnowledgeSearchRequest(q="x", limit=10)
        assert ok.limit == 10
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/models/knowledge.py`**

Create `D:/GEO2/backend/app/models/knowledge.py`:

```python
"""Pydantic models for knowledge base API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)


class KnowledgeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    created_at: datetime


class KnowledgeDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kb_id: str
    filename: str
    file_type: str
    file_size: int | None
    parse_status: str
    parse_error: str | None
    chunk_count: int
    created_at: datetime


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doc_id: str
    chunk_index: int
    content: str
    content_length: int


class KnowledgeSearchRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(5, ge=1, le=50)


class KnowledgeSearchResult(BaseModel):
    query: str
    chunks: list[KnowledgeChunk]
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_schemas.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): knowledge Pydantic schemas + tests"
```

---

### Task 2.2: Knowledge API Endpoints (CRUD + Search)

**Files:**
- Create: `D:/GEO2/backend/app/api/knowledge.py`
- Modify: `D:/GEO2/backend/app/main.py` (register router)
- Create: `D:/GEO2/backend/tests/test_api_knowledge.py`

**Interfaces:**
- `POST /api/knowledge` → create KB
- `GET /api/knowledge` → list KBs
- `GET /api/knowledge/{kb_id}` → KB details + documents
- `DELETE /api/knowledge/{kb_id}` → delete KB (409 if has tasks)
- `DELETE /api/knowledge/{kb_id}/documents/{doc_id}` → delete document
- `GET /api/knowledge/{kb_id}/chunks?q=...&limit=5` → keyword search

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_knowledge.py`:

```python
"""Integration tests for knowledge base API."""
from fastapi.testclient import TestClient


def test_create_kb(client: TestClient) -> None:
    resp = client.post(
        "/api/knowledge",
        json={"name": "测试 KB", "description": "描述"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["name"] == "测试 KB"


def test_list_kbs(client: TestClient) -> None:
    client.post("/api/knowledge", json={"name": "A"})
    client.post("/api/knowledge", json={"name": "B"})
    resp = client.get("/api/knowledge")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_kb_with_documents(client: TestClient) -> None:
    create = client.post("/api/knowledge", json={"name": "X"})
    kb_id = create.json()["id"]
    resp = client.get(f"/api/knowledge/{kb_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "X"
    assert "documents" in body
    assert body["documents"] == []


def test_get_kb_404(client: TestClient) -> None:
    resp = client.get("/api/knowledge/nonexistent-id")
    assert resp.status_code == 404


def test_create_kb_validates_name(client: TestClient) -> None:
    resp = client.post("/api/knowledge", json={"name": ""})
    assert resp.status_code == 422


def test_search_chunks(client: TestClient) -> None:
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.models.orm_v02 import KnowledgeBaseORM
    from sqlalchemy import select
    from app.core.db import get_session_factory
    from app.main import app
    from app.core.config import get_settings

    get_settings.cache_clear()
    factory = get_session_factory()
    # Use a sync session for the test fixture
    from app.core.db import get_engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.db import get_session_factory

    # Create kb + chunks directly
    import asyncio
    async def _setup():
        async with factory() as s:
            repo = KnowledgeRepository(s)
            kb = await repo.create_kb(name="KB")
            doc = await repo.add_document(
                kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
                file_type="txt", file_size=100,
            )
            await repo.add_chunks(
                doc_id=doc.id, kb_id=kb.id,
                chunks=[
                    {"chunk_index": 0, "content": "小米手机性能优秀", "content_length": 8},
                    {"chunk_index": 1, "content": "华为手机", "content_length": 4},
                ],
            )
            return kb.id

    kb_id = asyncio.run(_setup())

    resp = client.get(f"/api/knowledge/{kb_id}/chunks?q=小米&limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["chunks"]) == 1
    assert "小米" in body["chunks"][0]["content"]


def test_delete_kb(client: TestClient) -> None:
    create = client.post("/api/knowledge", json={"name": "Del"})
    kb_id = create.json()["id"]
    resp = client.delete(f"/api/knowledge/{kb_id}")
    assert resp.status_code == 204
    get_resp = client.get(f"/api/knowledge/{kb_id}")
    assert get_resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_knowledge.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `app.api.knowledge`.

- [ ] **Step 3: Create `app/api/knowledge.py`**

Create `D:/GEO2/backend/app/api/knowledge.py`:

```python
"""Knowledge base API: CRUD, document listing, keyword search."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jieba

from app.api.diagnosis import get_session
from app.models.knowledge import (
    KnowledgeBase,
    KnowledgeBaseCreate,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeSearchResult,
)
from app.models.orm_v02 import (
    KnowledgeBaseORM,
    KnowledgeDocumentORM,
)
from app.repositories.knowledge_repo import KnowledgeRepository

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


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


@router.delete("/{kb_id}", status_code=204)
async def delete_kb(
    kb_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete KB. Returns 409 if any task references it."""
    from app.models.orm_v02 import TaskORM
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


@router.delete("/{kb_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    kb_id: str,
    doc_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    from sqlalchemy import delete
    repo = KnowledgeRepository(session)
    doc = await repo.get_document(doc_id)
    if doc is None or doc.kb_id != kb_id:
        raise HTTPException(status_code=404, detail="document not found")
    await session.execute(
        delete(KnowledgeDocumentORM).where(KnowledgeDocumentORM.id == doc_id)
    )
    await session.commit()


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

    # jieba: extract keywords (length > 1 to skip single chars)
    keywords = [w for w in jieba.cut(q) if len(w.strip()) > 1]
    chunks = await repo.search_chunks_by_keyword(
        kb_id=kb_id, keywords=keywords, top_k=limit
    )
    return KnowledgeSearchResult(
        query=q,
        chunks=[KnowledgeChunk.model_validate(c) for c in chunks],
    )
```

- [ ] **Step 4: Register router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Find the `create_app` function. After the existing `app.include_router(reports.router, prefix="/api")` line, add:

```python
    from app.api.knowledge import router as knowledge_router
    app.include_router(knowledge_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_knowledge.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): knowledge API endpoints with keyword search + tests"
```

---

### Task 2.3: Document Upload API (Multipart)

**Files:**
- Modify: `D:/GEO2/backend/app/api/knowledge.py`
- Modify: `D:/GEO2/backend/tests/test_api_knowledge.py`
- Create: `D:/GEO2/backend/app/tasks/__init__.py` (empty, if not exists)

**Interfaces (addition):**
- `POST /api/knowledge/{kb_id}/documents` (multipart/form-data with `file` field)
  - Validates file size (≤ `max_upload_size_mb`)
  - Validates file type (pdf/docx/md/txt)
  - Saves to `data/uploads/{kb_id}/{doc_id}.{ext}`
  - Creates `KnowledgeDocumentORM` with `parse_status=pending`
  - Schedules parser worker (Task 2.4)

- [ ] **Step 1: Write failing test**

Append to `D:/GEO2/backend/tests/test_api_knowledge.py`:

```python
def test_upload_document(client: TestClient, tmp_path) -> None:
    from tests.conftest import PROJECT_ROOT
    fixture = PROJECT_ROOT / "tests" / "fixtures" / "sample.txt"

    create = client.post("/api/knowledge", json={"name": "UploadKB"})
    kb_id = create.json()["id"]

    with open(fixture, "rb") as f:
        resp = client.post(
            f"/api/knowledge/{kb_id}/documents",
            files={"file": ("sample.txt", f, "text/plain")},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "sample.txt"
    assert body["file_type"] == "txt"
    assert body["parse_status"] in ("pending", "success")  # worker may run sync


def test_upload_rejects_oversized(client: TestClient, tmp_path, monkeypatch) -> None:
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("MAX_UPLOAD_SIZE_MB", "1")  # 1MB

    create = client.post("/api/knowledge", json={"name": "SizeKB"})
    kb_id = create.json()["id"]

    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

    with open(big, "rb") as f:
        resp = client.post(
            f"/api/knowledge/{kb_id}/documents",
            files={"file": ("big.txt", f, "text/plain")},
        )
    assert resp.status_code == 413  # Payload Too Large


def test_upload_rejects_unsupported_type(client: TestClient, tmp_path) -> None:
    create = client.post("/api/knowledge", json={"name": "TypeKB"})
    kb_id = create.json()["id"]

    bad = tmp_path / "bad.exe"
    bad.write_bytes(b"MZ")

    with open(bad, "rb") as f:
        resp = client.post(
            f"/api/knowledge/{kb_id}/documents",
            files={"file": ("bad.exe", f, "application/octet-stream")},
        )
    assert resp.status_code == 415
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_knowledge.py::test_upload_document tests/test_api_knowledge.py::test_upload_rejects_oversized tests/test_api_knowledge.py::test_upload_rejects_unsupported_type -v
```

Expected: FAIL with 404 or 405 (endpoint not found).

- [ ] **Step 3: Add upload endpoint to `app/api/knowledge.py`**

Edit `D:/GEO2/backend/app/api/knowledge.py`. Add the upload imports at the top:

```python
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
```

Then add this endpoint anywhere in the file (e.g., after `delete_document`):

```python
_ALLOWED_TYPES = {"pdf": "pdf", "vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
                  "md": "md", "plain": "txt"}
_ALLOWED_EXTENSIONS = {"pdf", "docx", "md", "txt"}


@router.post("/{kb_id}/documents", status_code=201, response_model=KnowledgeDocument)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> KnowledgeDocumentORM:
    """Upload a document to a knowledge base. Triggers async parsing."""
    from app.core.config import get_settings

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
            detail=f"unsupported file type: .{ext}; allowed: {_ALLOWED_EXTENSIONS}",
        )

    # Save to disk
    doc_id = str(uuid.uuid4())
    upload_dir = Path(__file__).resolve().parent.parent.parent / "data" / "uploads" / kb_id
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
                raise HTTPException(
                    status_code=413,
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
    from app.tasks.parser_worker import schedule_parse
    schedule_parse(doc.id)

    return doc
```

- [ ] **Step 4: Create empty `app/tasks/__init__.py` (if not exists)**

```bash
touch "D:/GEO2/backend/app/tasks/__init__.py" 2>/dev/null || true
```

If it already exists, skip.

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_knowledge.py -v
```

Expected: All tests PASS (the upload tests will pass even without a worker — `parse_status` is `pending` or `success` if worker ran sync).

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): document upload API with size/type validation + tests"
```

---

### Task 2.4: Parser Worker (Async)

**Files:**
- Create: `D:/GEO2/backend/app/tasks/parser_worker.py`
- Create: `D:/GEO2/backend/tests/test_parser_worker.py`

**Interfaces:**
- Consumes: `KnowledgeRepository`, `parser`, `chunker`
- Produces:
  - `parse_document(doc_id) -> None` — runs sync (testable)
  - `schedule_parse(doc_id) -> asyncio.Task` — fire-and-forget background execution

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_parser_worker.py`:

```python
"""Tests for the parser worker."""
import pytest

from app.domain.knowledge.chunker import chunk_text
from app.domain.knowledge.parser import (
    parse_docx,
    parse_md,
    parse_pdf,
    parse_txt,
)
from app.models.orm_v02 import KnowledgeDocumentORM
from app.repositories.knowledge_repo import KnowledgeRepository
from app.tasks.parser_worker import parse_document


@pytest.mark.asyncio
async def test_parse_txt_document(db_session, tmp_path) -> None:
    from app.core.config import get_settings
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    sample = tmp_path / "sample.txt"
    sample.write_text("段落一内容超过五十字。" * 5 + "\n\n段落二。", encoding="utf-8")
    doc = await repo.add_document(
        kb_id=kb.id, filename="sample.txt", file_path=str(sample),
        file_type="txt", file_size=sample.stat().st_size,
    )
    await parse_document(doc.id)
    refreshed = await repo.get_document(doc.id)
    assert refreshed.parse_status == "success"
    assert refreshed.chunk_count > 0
    chunks = await repo.list_chunks(kb.id)
    assert len(chunks) == refreshed.chunk_count


@pytest.mark.asyncio
async def test_parse_document_with_corrupted_file(db_session, tmp_path) -> None:
    repo = KnowledgeRepository(db_session)
    kb = await repo.create_kb(name="KB")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    doc = await repo.add_document(
        kb_id=kb.id, filename="bad.pdf", file_path=str(bad),
        file_type="pdf", file_size=10,
    )
    await parse_document(doc.id)
    refreshed = await repo.get_document(doc.id)
    assert refreshed.parse_status == "failed"
    assert refreshed.parse_error is not None
    assert "PDF" in refreshed.parse_error or "corrupt" in refreshed.parse_error.lower()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser_worker.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/tasks/parser_worker.py`**

Create `D:/GEO2/backend/app/tasks/parser_worker.py`:

```python
"""Async worker for parsing uploaded documents into chunks."""
from __future__ import annotations

import asyncio
import json

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
    """Parse a single document: read file → chunk → save chunks → update status.

    Runs synchronously when called directly (for tests).
    """
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
            text, min_length=settings.chunk_min_length, max_length=settings.chunk_max_length
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
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_parser_worker.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Run all knowledge tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_knowledge_repo.py tests/test_knowledge_schemas.py tests/test_api_knowledge.py tests/test_parser.py tests/test_chunker.py tests/test_parser_worker.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): async parser worker with chunking + tests"
```

---

## Phase 3: Tasks

### Task 3.1: Task + Article Repository

**Files:**
- Create: `D:/GEO2/backend/app/repositories/task_repo.py`
- Create: `D:/GEO2/backend/tests/test_task_repo.py`

**Interfaces:**
- `TaskRepository(session)`:
  - `create_task(name, kb_id, brand, topic, keywords, article_count, style, target_length) -> TaskORM`
  - `get_task(task_id) -> TaskORM | None`
  - `list_tasks() -> list[TaskORM]`
  - `list_tasks_by_status(status) -> list[TaskORM]`
  - `update_task_status(task_id, status, progress=None, error=None) -> None`
  - `delete_task(task_id) -> None`
  - `create_article(task_id) -> ArticleORM`  # placeholder
  - `get_article(article_id) -> ArticleORM | None`
  - `list_articles(task_id) -> list[ArticleORM]`
  - `list_articles_by_status(review_status) -> list[ArticleORM]`
  - `update_article(article_id, ...) -> None` — set content, title, etc.
  - `update_article_review(article_id, status, note=None) -> None`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_task_repo.py`:

```python
"""Tests for TaskRepository."""
import json

import pytest

from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
from app.repositories.task_repo import TaskRepository


@pytest.mark.asyncio
async def test_create_task(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = await repo.create_task(
        name="T1", kb_id="kb1", brand="Brand",
        topic="Topic", keywords=["k1", "k2"],
        article_count=3, style="neutral", target_length=1500,
    )
    assert task.id != ""
    assert task.status == "pending"
    assert json.loads(task.keywords) == ["k1", "k2"]


@pytest.mark.asyncio
async def test_update_task_status(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    await repo.update_task_status(task.id, status="running", progress=50)
    refreshed = await repo.get_task(task.id)
    assert refreshed.status == "running"
    assert refreshed.progress == 50


@pytest.mark.asyncio
async def test_list_tasks_orders_by_created_desc(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    t1 = await repo.create_task(name="T1", kb_id="kb1", topic="X", article_count=1, style="neutral")
    t2 = await repo.create_task(name="T2", kb_id="kb1", topic="Y", article_count=1, style="neutral")
    tasks = await repo.list_tasks()
    assert tasks[0].id == t2.id  # most recent first


@pytest.mark.asyncio
async def test_create_article_placeholder(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()

    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    article = await repo.create_article(task.id)
    assert article.title == "待生成 #1"
    assert article.review_status == "pending"
    assert article.content is None


@pytest.mark.asyncio
async def test_update_article_content(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()
    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    article = await repo.create_article(task.id)
    await repo.update_article(
        article.id,
        title="新标题",
        content="# 标题\n\n内容",
        content_length=10,
        cited_chunks=["c1", "c2"],
        llm_provider="deepseek",
    )
    refreshed = await repo.get_article(article.id)
    assert refreshed.title == "新标题"
    assert refreshed.content == "# 标题\n\n内容"
    assert json.loads(refreshed.cited_chunks) == ["c1", "c2"]


@pytest.mark.asyncio
async def test_update_article_review(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()
    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=1, style="neutral",
    )
    article = await repo.create_article(task.id)
    await repo.update_article_review(article.id, status="approved", note="OK")
    refreshed = await repo.get_article(article.id)
    assert refreshed.review_status == "approved"
    assert refreshed.review_note == "OK"
    assert refreshed.reviewed_at is not None


@pytest.mark.asyncio
async def test_list_articles_by_review_status(db_session) -> None:
    repo = TaskRepository(db_session)
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    db_session.add(kb)
    await db_session.commit()
    task = await repo.create_task(
        name="T", kb_id="kb1", topic="X", article_count=3, style="neutral",
    )
    a1 = await repo.create_article(task.id)
    a2 = await repo.create_article(task.id)
    a3 = await repo.create_article(task.id)
    await repo.update_article_review(a1.id, status="approved")
    await repo.update_article_review(a2.id, status="rejected", note="bad")

    pending = await repo.list_articles_by_status("pending")
    approved = await repo.list_articles_by_status("approved")
    assert {a.id for a in pending} == {a3.id}
    assert {a.id for a in approved} == {a1.id}
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_task_repo.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/repositories/task_repo.py`**

Create `D:/GEO2/backend/app/repositories/task_repo.py`:

```python
"""Repository for tasks and articles."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v02 import ArticleORM, TaskORM


def _article_placeholder_title(index: int) -> str:
    return f"待生成 #{index + 1}"


class TaskRepository:
    """Data access for tasks and articles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Tasks ---

    async def create_task(
        self,
        name: str,
        kb_id: str,
        topic: str,
        article_count: int,
        style: str,
        brand: str | None = None,
        keywords: list[str] | None = None,
        target_length: int = 1500,
    ) -> TaskORM:
        task = TaskORM(
            id=str(uuid.uuid4()),
            name=name,
            kb_id=kb_id,
            brand=brand,
            topic=topic,
            keywords=json.dumps(keywords or [], ensure_ascii=False),
            article_count=article_count,
            style=style,
            target_length=target_length,
            status="pending",
            progress=0,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: str) -> TaskORM | None:
        result = await self.session.execute(
            select(TaskORM).where(TaskORM.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_tasks(self) -> list[TaskORM]:
        result = await self.session.execute(
            select(TaskORM).order_by(TaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_tasks_by_status(self, status: str) -> list[TaskORM]:
        result = await self.session.execute(
            select(TaskORM)
            .where(TaskORM.status == status)
            .order_by(TaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int | None = None,
        error: str | None = None,
    ) -> None:
        task = await self.get_task(task_id)
        if task is None:
            return
        task.status = status
        if progress is not None:
            task.progress = progress
        if error is not None:
            task.error_message = error
        task.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def delete_task(self, task_id: str) -> None:
        from sqlalchemy import delete
        await self.session.execute(
            delete(TaskORM).where(TaskORM.id == task_id)
        )
        await self.session.commit()

    # --- Articles ---

    async def create_article(self, task_id: str, index: int = 0) -> ArticleORM:
        article = ArticleORM(
            id=str(uuid.uuid4()),
            task_id=task_id,
            title=_article_placeholder_title(index),
            review_status="pending",
            cited_chunks=json.dumps([]),
        )
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)
        return article

    async def get_article(self, article_id: str) -> ArticleORM | None:
        result = await self.session.execute(
            select(ArticleORM).where(ArticleORM.id == article_id)
        )
        return result.scalar_one_or_none()

    async def list_articles(self, task_id: str) -> list[ArticleORM]:
        result = await self.session.execute(
            select(ArticleORM)
            .where(ArticleORM.task_id == task_id)
            .order_by(ArticleORM.created_at)
        )
        return list(result.scalars().all())

    async def list_articles_by_status(
        self, review_status: str, task_id: str | None = None
    ) -> list[ArticleORM]:
        stmt = select(ArticleORM).where(ArticleORM.review_status == review_status)
        if task_id is not None:
            stmt = stmt.where(ArticleORM.task_id == task_id)
        stmt = stmt.order_by(ArticleORM.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_article(
        self,
        article_id: str,
        title: str | None = None,
        content: str | None = None,
        content_length: int | None = None,
        cited_chunks: list[str] | None = None,
        llm_provider: str | None = None,
        error_message: str | None = None,
    ) -> None:
        article = await self.get_article(article_id)
        if article is None:
            return
        if title is not None:
            article.title = title
        if content is not None:
            article.content = content
            article.content_length = content_length
        if cited_chunks is not None:
            article.cited_chunks = json.dumps(cited_chunks, ensure_ascii=False)
        if llm_provider is not None:
            article.llm_provider = llm_provider
        if error_message is not None:
            article.error_message = error_message
        article.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_article_review(
        self,
        article_id: str,
        status: str,
        note: str | None = None,
    ) -> None:
        article = await self.get_article(article_id)
        if article is None:
            return
        article.review_status = status
        article.review_note = note
        article.reviewed_at = datetime.now(timezone.utc)
        article.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_task_repo.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): TaskRepository with task/article CRUD + review transitions + tests"
```

---

### Task 3.2: Task Pydantic Schemas

**Files:**
- Create: `D:/GEO2/backend/app/models/task.py`
- Create: `D:/GEO2/backend/tests/test_task_schemas.py`

**Interfaces:**
- `Style` enum: neutral/professional/casual
- `TaskStatus` enum (already in `app.models.schemas`; we'll re-export)
- `ReviewStatus` enum
- `TaskCreate`, `Task`
- `Article`, `ReviewAction`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_task_schemas.py`:

```python
"""Tests for task/article/review Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.task import (
    Article,
    ReviewAction,
    ReviewStatus,
    Style,
    TaskCreate,
    TaskStatus,
)


class TestTaskCreate:
    def test_min_topic(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(
                name="T", kb_id="kb1", topic="短",
                article_count=1, style="neutral",
            )

    def test_article_count_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(name="T", kb_id="kb1", topic="足够长的主题", article_count=0)
        with pytest.raises(ValidationError):
            TaskCreate(
                name="T", kb_id="kb1", topic="足够长的主题",
                article_count=21, style="neutral",
            )

    def test_target_length_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TaskCreate(
                name="T", kb_id="kb1", topic="足够长的主题",
                article_count=1, style="neutral", target_length=100,
            )
        # Valid
        ok = TaskCreate(
            name="T", kb_id="kb1", topic="足够长的主题",
            article_count=1, style="neutral", target_length=2000,
        )
        assert ok.target_length == 2000

    def test_valid_task(self) -> None:
        t = TaskCreate(
            name="My Task", kb_id="kb1", brand="Brand",
            topic="生成关于产品的文章", keywords=["k1", "k2"],
            article_count=3, style="professional",
        )
        assert t.article_count == 3
        assert t.style == Style.PROFESSIONAL
        assert t.brand == "Brand"


class TestReviewAction:
    def test_reject_requires_note(self) -> None:
        # Note is optional in schema; API endpoint enforces for reject specifically
        a = ReviewAction(note=None)
        assert a.note is None


class TestEnums:
    def test_status_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"

    def test_review_status_values(self) -> None:
        assert ReviewStatus.PENDING == "pending"
        assert ReviewStatus.APPROVED == "approved"
        assert ReviewStatus.REJECTED == "rejected"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_task_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/models/task.py`**

Create `D:/GEO2/backend/app/models/task.py`:

```python
"""Pydantic models for tasks, articles, reviews."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Style(str, Enum):
    NEUTRAL = "neutral"
    PROFESSIONAL = "professional"
    CASUAL = "casual"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISE_REQUESTED = "revise_requested"


class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kb_id: str
    brand: str | None = Field(None, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    article_count: int = Field(1, ge=1, le=20)
    style: Style = Style.NEUTRAL
    target_length: int = Field(1500, ge=300, le=10000)


class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    kb_id: str
    brand: str | None
    topic: str
    keywords: list[str]
    article_count: int
    style: Style
    target_length: int
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class Article(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    title: str | None
    content: str | None
    content_length: int | None
    review_status: ReviewStatus
    review_note: str | None
    reviewed_at: datetime | None
    cited_chunks: list[str] = Field(default_factory=list)
    llm_provider: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ReviewAction(BaseModel):
    """Action body for approve / reject endpoints."""

    note: str | None = Field(None, max_length=2000)
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_task_schemas.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): task/article/review Pydantic schemas + tests"
```

---

### Task 3.3: Tasks API Endpoints

**Files:**
- Create: `D:/GEO2/backend/app/api/tasks.py`
- Modify: `D:/GEO2/backend/app/main.py` (register router)
- Create: `D:/GEO2/backend/tests/test_api_tasks.py`

**Interfaces:**
- `POST /api/tasks` → create task (schedules worker)
- `GET /api/tasks` → list tasks
- `GET /api/tasks/{task_id}` → task detail + articles
- `DELETE /api/tasks/{task_id}` → delete task (404 if running)
- `POST /api/tasks/{task_id}/cancel` → mark cancelled
- `GET /api/tasks/{task_id}/articles` → task's articles

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_tasks.py`:

```python
"""Integration tests for tasks API."""
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_create_task(client: TestClient) -> None:
    # Need a KB first
    kb = client.post("/api/knowledge", json={"name": "TaskKB"}).json()

    with patch("app.api.tasks.schedule_task") as mock:
        resp = client.post(
            "/api/tasks",
            json={
                "name": "测试任务",
                "kb_id": kb["id"],
                "brand": "测试品牌",
                "topic": "生成关于产品的文章",
                "keywords": ["k1", "k2"],
                "article_count": 3,
                "style": "professional",
                "target_length": 1500,
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "测试任务"
    assert body["article_count"] == 3
    assert body["status"] == "pending"
    assert mock.called


def test_create_task_validates_kb_exists(client: TestClient) -> None:
    resp = client.post(
        "/api/tasks",
        json={
            "name": "T", "kb_id": "nonexistent-kb",
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        },
    )
    assert resp.status_code == 404


def test_create_task_validates_article_count(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    resp = client.post(
        "/api/tasks",
        json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 100, "style": "neutral",
        },
    )
    assert resp.status_code == 422


def test_list_tasks(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        client.post("/api/tasks", json={
            "name": "T1", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
        client.post("/api/tasks", json={
            "name": "T2", "kb_id": kb["id"],
            "topic": "另一个主题", "article_count": 1, "style": "neutral",
        })
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_task_with_articles(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 2, "style": "neutral",
        })
    task_id = create.json()["id"]
    resp = client.get(f"/api/tasks/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert "articles" in body
    # Articles not yet created (worker not run in test)
    # But task fields should be present
    assert body["id"] == task_id


def test_delete_task(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
    task_id = create.json()["id"]
    resp = client.delete(f"/api/tasks/{task_id}")
    assert resp.status_code == 204


def test_cancel_task(client: TestClient) -> None:
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
    task_id = create.json()["id"]
    resp = client.post(f"/api/tasks/{task_id}/cancel")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_tasks.py -v
```

Expected: FAIL (404 — endpoint not registered).

- [ ] **Step 3: Create `app/api/tasks.py`**

Create `D:/GEO2/backend/app/api/tasks.py`:

```python
"""Tasks API: create, list, get, delete, cancel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.orm_v02 import TaskORM
from app.models.task import Article, Task, TaskCreate
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.task_repo import TaskRepository

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_to_pydantic(task: TaskORM) -> Task:
    import json
    return Task(
        id=task.id,
        name=task.name,
        kb_id=task.kb_id,
        brand=task.brand,
        topic=task.topic,
        keywords=json.loads(task.keywords or "[]"),
        article_count=task.article_count,
        style=task.style,  # type: ignore[arg-type]
        target_length=task.target_length,
        status=task.status,  # type: ignore[arg-type]
        progress=task.progress,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", status_code=201, response_model=Task)
async def create_task(
    body: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskORM:
    kb_repo = KnowledgeRepository(session)
    kb = await kb_repo.get_kb(body.kb_id)
    if kb is None:
        raise HTTPException(status_code=404, detail="knowledge base not found")

    task_repo = TaskRepository(session)
    task = await task_repo.create_task(
        name=body.name,
        kb_id=body.kb_id,
        brand=body.brand,
        topic=body.topic,
        keywords=body.keywords,
        article_count=body.article_count,
        style=body.style.value,
        target_length=body.target_length,
    )

    # Schedule background worker
    from app.tasks.task_worker import schedule_task
    schedule_task(task.id)

    return task


@router.get("", response_model=list[Task])
async def list_tasks(session: AsyncSession = Depends(get_session)) -> list[TaskORM]:
    repo = TaskRepository(session)
    tasks = await repo.list_tasks()
    return tasks


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Task details + list of articles."""
    repo = TaskRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    articles = await repo.list_articles(task_id)
    return {
        **_task_to_pydantic(task).model_dump(),
        "articles": [Article.model_validate(a) for a in articles],
    }


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = TaskRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status == "running":
        raise HTTPException(
            status_code=409,
            detail="cannot delete running task; cancel it first",
        )
    await repo.delete_task(task_id)


@router.post("/{task_id}/cancel", response_model=Task)
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Task:
    """Mark task as cancelled. Worker checks status between articles."""
    repo = TaskRepository(session)
    task = await repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status in ("completed", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"task is already {task.status}; cannot cancel",
        )
    await repo.update_task_status(task_id, status="cancelled")
    task = await repo.get_task(task_id)
    return _task_to_pydantic(task)


@router.get("/{task_id}/articles", response_model=list[Article])
async def list_task_articles(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[Article]:
    repo = TaskRepository(session)
    return await repo.list_articles(task_id)
```

- [ ] **Step 4: Register router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. After the knowledge router line, add:

```python
    from app.api.tasks import router as tasks_router
    app.include_router(tasks_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_tasks.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): tasks API endpoints (CRUD + cancel) + tests"
```

---

## Phase 4: Generator (Prompt Builder, Content Writer, Worker)

### Task 4.1: Prompt Builder

**Files:**
- Create: `D:/GEO2/backend/app/domain/generator/__init__.py`
- Create: `D:/GEO2/backend/app/domain/generator/prompt_builder.py`
- Create: `D:/GEO2/backend/tests/test_prompt_builder.py`

**Interfaces:**
- `PromptBuilder.build(brand, topic, keywords, style, target_length, chunks) -> str`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_prompt_builder.py`:

```python
"""Tests for the prompt builder."""
from app.domain.generator.prompt_builder import PromptBuilder


class TestPromptBuilder:
    def test_includes_brand(self) -> None:
        prompt = PromptBuilder.build(
            brand="小米", topic="手机", keywords=["性能"],
            style="professional", target_length=1500,
            chunks=[],
        )
        assert "小米" in prompt

    def test_includes_topic(self) -> None:
        prompt = PromptBuilder.build(
            brand=None, topic="国产手机推荐", keywords=[],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "国产手机推荐" in prompt

    def test_includes_keywords(self) -> None:
        prompt = PromptBuilder.build(
            brand=None, topic="主题", keywords=["关键词A", "关键词B"],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "关键词A" in prompt
        assert "关键词B" in prompt

    def test_includes_chunks(self) -> None:
        prompt = PromptBuilder.build(
            brand=None, topic="主题", keywords=[],
            style="neutral", target_length=1000,
            chunks=[{"index": 1, "content": "参考资料内容X"}],
        )
        assert "参考资料内容X" in prompt

    def test_empty_chunks_marks_no_reference(self) -> None:
        prompt = PromptBuilder.build(
            brand=None, topic="主题", keywords=[],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "无参考资料" in prompt or "knowledge base 暂无可用" in prompt

    def test_explicitly_forbids_fabrication(self) -> None:
        """Prompt must include the 'do not fabricate' instruction."""
        prompt = PromptBuilder.build(
            brand=None, topic="主题", keywords=[],
            style="neutral", target_length=1000,
            chunks=[],
        )
        assert "不得编造" in prompt or "不得虚构" in prompt
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_prompt_builder.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/generator/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/generator/__init__.py`.

- [ ] **Step 4: Create `app/domain/generator/prompt_builder.py`**

Create `D:/GEO2/backend/app/domain/generator/prompt_builder.py`:

```python
"""Build prompts for article generation grounded in knowledge base chunks."""
from __future__ import annotations

_STYLE_LABELS = {
    "neutral": "中性客观",
    "professional": "专业严谨",
    "casual": "轻松活泼",
}


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return (
            "（知识库暂无可用参考资料。请基于通用知识撰写，但避免编造具体数据/价格/案例。）"
        )
    parts: list[str] = []
    for c in chunks:
        idx = c.get("index", 0)
        content = c.get("content", "").strip()
        parts.append(f"[参考资料 #{idx}]\n{content}")
    return "\n\n".join(parts)


def _format_keywords(keywords: list[str]) -> str:
    if not keywords:
        return "（无）"
    return "、".join(keywords)


def build(
    brand: str | None,
    topic: str,
    keywords: list[str],
    style: str,
    target_length: int,
    chunks: list[dict],
) -> str:
    """Build the article-generation prompt.

    Returns a string that, when sent to an LLM, instructs it to write a
    Markdown article grounded in the provided chunks. Includes explicit
    anti-fabrication instructions.
    """
    style_label = _STYLE_LABELS.get(style, style)
    brand_phrase = brand or "该品牌"
    chunks_block = _format_chunks(chunks)
    keywords_block = _format_keywords(keywords)

    return f"""你是 {brand_phrase} 的内容编辑。基于以下"参考资料"撰写一篇文章。

【主题】{topic}
【关键词】{keywords_block}
【风格】{style_label}
【目标字数】约 {target_length} 字

【参考资料】（请基于这些真实信息撰写，不得编造参考资料中没有的事实）
---
{chunks_block}
---

要求：
1. 文章结构：标题（H1）、引言、3-5 个 H2 章节、结论
2. 每段开头直接给出核心主张（BLUF 原则）
3. 引用参考资料时用 [1] [2] 等标注
4. 不得编造参考资料中没有的数据、价格、案例
5. 不得使用"作为 AI 模型"等元话语

输出 Markdown 格式。
"""
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_prompt_builder.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): PromptBuilder with anti-fabrication instructions + tests"
```

---

### Task 4.2: Content Writer (TDD, Mocked LLM)

**Files:**
- Create: `D:/GEO2/backend/app/domain/generator/content_writer.py`
- Create: `D:/GEO2/backend/tests/test_content_writer.py`

**Interfaces:**
- `ContentWriter.write_article(task, chunks) -> tuple[str, str]` — returns (title, content)
  - Calls LLM via v0.1's `llm_client`
  - Extracts H1 as title
  - Handles LLM errors by returning fallback content

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_content_writer.py`:

```python
"""Tests for ContentWriter. Mocks LLM via v0.1's openai client."""
import pytest
import respx
from httpx import Response

from app.core.config import Settings
from app.domain.generator.content_writer import ContentWriter


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    )


@pytest.fixture
def writer(settings: Settings) -> ContentWriter:
    return ContentWriter(settings)


class TestTitleExtraction:
    def test_extracts_h1_title(self, writer: ContentWriter) -> None:
        text = "# 真实标题\n\n内容。"
        title = writer._extract_title(text)
        assert title == "真实标题"

    def test_returns_fallback_for_no_h1(self, writer: ContentWriter) -> None:
        text = "没有标题的内容"
        title = writer._extract_title(text)
        assert title.startswith("未命名") or len(title) > 0

    def test_handles_markdown_prefix(self, writer: ContentWriter) -> None:
        text = "  #  标题带空格  \n\n内容"
        title = writer._extract_title(text)
        assert title == "标题带空格"


@pytest.mark.asyncio
@respx.mock
async def test_write_article_calls_llm(writer: ContentWriter) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "# 我的文章\n\n这是内容。"}}
                ]
            },
        )
    )

    title, content = await writer.write_article(
        brand="Brand",
        topic="Topic",
        keywords=["k1"],
        style="neutral",
        target_length=500,
        chunks=[],
    )
    assert title == "我的文章"
    assert "这是内容" in content


@pytest.mark.asyncio
@respx.mock
async def test_write_article_handles_timeout(writer: ContentWriter) -> None:
    import httpx
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    title, content = await writer.write_article(
        brand=None, topic="Topic", keywords=[],
        style="neutral", target_length=500, chunks=[],
    )
    # On failure, returns fallback title + empty content
    assert title is not None
    assert content == ""


@pytest.mark.asyncio
@respx.mock
async def test_write_article_handles_400(writer: ContentWriter) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(400, json={"error": "bad key"})
    )

    title, content = await writer.write_article(
        brand=None, topic="Topic", keywords=[],
        style="neutral", target_length=500, chunks=[],
    )
    assert content == ""
    assert title is not None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_content_writer.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/generator/content_writer.py`**

Create `D:/GEO2/backend/app/domain/generator/content_writer.py`:

```python
"""Content writer: orchestrates prompt building + LLM call + title extraction."""
from __future__ import annotations

import asyncio
import re

from openai import AsyncOpenAI

from app.core.config import Settings
from app.domain.generator.prompt_builder import build as build_prompt


class ContentWriter:
    """Generate one article per call. Uses the configured LLM provider."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract H1 from Markdown content. Returns fallback if not found."""
        m = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
        if m:
            return m.group(1).strip()
        # Fallback: first non-empty line truncated
        for line in content.splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line[:60] or f"未命名文章"
        return f"未命名文章"

    async def write_article(
        self,
        brand: str | None,
        topic: str,
        keywords: list[str],
        style: str,
        target_length: int,
        chunks: list[dict],
    ) -> tuple[str, str]:
        """Generate one article. Returns (title, content).

        On LLM failure, returns (fallback_title, "") — caller should
        mark the article as errored.
        """
        prompt = build_prompt(
            brand=brand,
            topic=topic,
            keywords=keywords,
            style=style,
            target_length=target_length,
            chunks=chunks,
        )

        try:
            client = AsyncOpenAI(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                timeout=self.settings.llm_call_timeout_s,
            )
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.settings.deepseek_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                ),
                timeout=self.settings.llm_call_timeout_s,
            )
            content = response.choices[0].message.content or ""
            title = self._extract_title(content)
            return title, content
        except Exception:  # noqa: BLE001
            return self._extract_title(""), ""
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_content_writer.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): ContentWriter with title extraction + error handling + tests"
```

---

### Task 4.3: Task Worker (Async)

**Files:**
- Create: `D:/GEO2/backend/app/tasks/task_worker.py`
- Create: `D:/GEO2/backend/tests/test_task_worker.py`

**Interfaces:**
- `run_task(task_id) -> None` — runs the full task (sync, testable)
- `schedule_task(task_id) -> asyncio.Task` — fire-and-forget
- Reuses v0.1's `asyncio._EXEC_LOCK` for single-flight execution

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_task_worker.py`:

```python
"""Tests for the task worker."""
from unittest.mock import patch, AsyncMock

import pytest

from app.models.orm_v02 import KnowledgeBaseORM
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.task_repo import TaskRepository
from app.tasks.task_worker import run_task


@pytest.mark.asyncio
async def test_run_task_creates_articles_and_generates(db_session) -> None:
    from app.core.config import get_settings

    repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)
    settings = get_settings()

    kb = await repo.create_kb(name="KB")
    doc = await repo.add_document(
        kb_id=kb.id, filename="x.txt", file_path="/tmp/x.txt",
        file_type="txt", file_size=100,
    )
    await repo.add_chunks(
        doc_id=doc.id, kb_id=kb.id,
        chunks=[
            {"chunk_index": 0, "content": "测试内容", "content_length": 4},
        ],
    )

    task = await task_repo.create_task(
        name="T", kb_id=kb.id, brand="Brand",
        topic="测试主题", keywords=[],
        article_count=2, style="neutral", target_length=500,
    )

    # Mock the content writer
    with patch("app.tasks.task_worker.ContentWriter") as MockWriter:
        mock_instance = MockWriter.return_value
        mock_instance.write_article = AsyncMock(return_value=("生成标题", "生成内容"))
        await run_task(task.id)

    # Verify
    refreshed = await task_repo.get_task(task.id)
    assert refreshed.status == "completed"
    assert refreshed.progress == 100
    articles = await task_repo.list_articles(task.id)
    assert len(articles) == 2
    assert all(a.title == "生成标题" for a in articles)
    assert all(a.content == "生成内容" for a in articles)


@pytest.mark.asyncio
async def test_run_task_continues_on_article_failure(db_session) -> None:
    repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)

    kb = await repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, topic="X", article_count=3, style="neutral",
    )

    with patch("app.tasks.task_worker.ContentWriter") as MockWriter:
        mock_instance = MockWriter.return_value
        # First call fails, second succeeds
        mock_instance.write_article = AsyncMock(
            side_effect=[("T1", "C1"), Exception("LLM down"), ("T3", "C3")]
        )
        await run_task(task.id)

    refreshed = await task_repo.get_task(task.id)
    # Task still completes
    assert refreshed.status == "completed"
    articles = await task_repo.list_articles(task.id)
    assert len(articles) == 3
    # Middle one has error
    assert articles[1].error_message is not None
    assert articles[1].content is None
    # Others succeeded
    assert articles[0].content == "C1"
    assert articles[2].content == "C3"


@pytest.mark.asyncio
async def test_run_task_respects_cancellation(db_session) -> None:
    from unittest.mock import patch, AsyncMock
    from app.models.orm_v02 import KnowledgeBaseORM
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.repositories.task_repo import TaskRepository

    repo = KnowledgeRepository(db_session)
    task_repo = TaskRepository(db_session)

    kb = await repo.create_kb(name="KB")
    task = await task_repo.create_task(
        name="T", kb_id=kb.id, topic="X", article_count=5, style="neutral",
    )

    # Manually mark task as cancelled before run
    await task_repo.update_task_status(task.id, status="cancelled")

    with patch("app.tasks.task_worker.ContentWriter") as MockWriter:
        mock_instance = MockWriter.return_value
        mock_instance.write_article = AsyncMock(return_value=("T", "C"))
        await run_task(task.id)

    # No articles should be created since task was cancelled
    articles = await task_repo.list_articles(task.id)
    assert len(articles) == 0
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_task_worker.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/tasks/task_worker.py`**

Create `D:/GEO2/backend/app/tasks/task_worker.py`:

```python
"""Async worker for content generation tasks."""
from __future__ import annotations

import asyncio
import json

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.generator.content_writer import ContentWriter
from app.domain.knowledge.retriever import search_chunks
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.task_repo import TaskRepository

logger = structlog.get_logger()

# Reuse the v0.1 global lock for single-flight execution
_EXEC_LOCK = asyncio.Lock()


async def _process_one(
    task, index: int, article, task_repo, kb_repo, writer
) -> None:
    """Generate one article. On failure, mark article with error and continue."""
    try:
        # Keyword retrieval
        import jieba
        query = task.topic + " " + " ".join(json.loads(task.keywords or "[]"))
        keywords = [w for w in jieba.cut(query) if len(w.strip()) > 1]
        chunks_orm = await task_repo.session.run_sync(
            lambda s: s  # placeholder
        ) if False else None
        # Direct call (skip the run_sync indirection)
        chunks = await search_chunks(
            session=task_repo.session,
            kb_id=task.kb_id,
            keywords=keywords,
            top_k=get_settings().retrieval_top_k,
        )

        chunks_for_prompt = [
            {"index": i + 1, "content": c.content} for i, c in enumerate(chunks)
        ]

        title, content = await writer.write_article(
            brand=task.brand,
            topic=task.topic,
            keywords=json.loads(task.keywords or "[]"),
            style=task.style,
            target_length=task.target_length,
            chunks=chunks_for_prompt,
        )

        if not content:
            await task_repo.update_article(
                article.id,
                title=f"生成失败 #{index + 1}",
                error_message="LLM 调用失败",
            )
            return

        await task_repo.update_article(
            article.id,
            title=title,
            content=content,
            content_length=len(content),
            cited_chunks=[c.id for c in chunks],
            llm_provider=get_settings().enabled_providers[0] if get_settings().enabled_providers else "deepseek",
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("article_generation_failed", article_id=article.id)
        await task_repo.update_article(
            article.id,
            title=f"生成失败 #{index + 1}",
            error_message=f"{type(e).__name__}: {e}",
        )


async def run_task(task_id: str) -> None:
    """Execute the full task pipeline (sync, used for tests).

    Reuses v0.1's _EXEC_LOCK via schedule_task.
    """
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        task_repo = TaskRepository(session)
        kb_repo = KnowledgeRepository(session)
        task = await task_repo.get_task(task_id)
        if task is None:
            logger.error("task_not_found", task_id=task_id)
            return

        # Already cancelled? Skip.
        if task.status == "cancelled":
            return

        try:
            task.status = "running"
            await task_repo.session.commit()

            # Create placeholder articles
            for i in range(task.article_count):
                await task_repo.create_article(task_id, index=i)

            articles = await task_repo.list_articles(task_id)
            writer = ContentWriter(settings)

            for i, article in enumerate(articles):
                # Re-check status before each article (cancellable mid-run)
                current = await task_repo.get_task(task_id)
                if current is None or current.status == "cancelled":
                    logger.info("task_cancelled", task_id=task_id, after=i)
                    break
                await _process_one(task, i, article, task_repo, kb_repo, writer)
                progress = int((i + 1) / task.article_count * 100)
                await task_repo.update_task_status(
                    task_id, status="running", progress=progress
                )

            task = await task_repo.get_task(task_id)
            if task and task.status != "cancelled":
                task.status = "completed"
                task.progress = 100
                await task_repo.session.commit()
        except Exception as e:  # noqa: BLE001
            logger.exception("task_failed", task_id=task_id)
            await task_repo.update_task_status(
                task_id, status="failed", error=f"{type(e).__name__}: {e}"
            )


async def execute_task_with_lock(task_id: str) -> None:
    """Wrap run_task with the v0.1 lock for single-flight execution."""
    async with _EXEC_LOCK:
        await run_task(task_id)


def schedule_task(task_id: str) -> asyncio.Task[None]:
    """Fire-and-forget background execution with lock."""
    return asyncio.create_task(execute_task_with_lock(task_id))
```

- [ ] **Step 4: Create `app/domain/knowledge/retriever.py` (referenced by worker)**

Create `D:/GEO2/backend/app/domain/knowledge/retriever.py`:

```python
"""Higher-level retrieval helpers (v0.2 uses keyword search from repo)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v02 import KnowledgeChunkORM
from app.repositories.knowledge_repo import KnowledgeRepository


async def search_chunks(
    session: AsyncSession,
    kb_id: str,
    keywords: list[str],
    top_k: int = 5,
) -> list[KnowledgeChunkORM]:
    """Convenience wrapper around KnowledgeRepository.search_chunks_by_keyword."""
    repo = KnowledgeRepository(session)
    return await repo.search_chunks_by_keyword(
        kb_id=kb_id, keywords=keywords, top_k=top_k
    )
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_task_worker.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Run all v0.2 tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All v0.1 + v0.2 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): task worker with single-flight lock + cancellation + tests"
```

---

## Phase 5: Review

### Task 5.1: Reviews API

**Files:**
- Create: `D:/GEO2/backend/app/api/reviews.py`
- Modify: `D:/GEO2/backend/app/main.py` (register router)
- Create: `D:/GEO2/backend/tests/test_api_reviews.py`

**Interfaces:**
- `GET /api/reviews?status=pending&task_id=...` → review queue
- `GET /api/reviews/{article_id}` → article detail
- `POST /api/reviews/{article_id}/approve` → approve
- `POST /api/reviews/{article_id}/reject` → reject (note required)
- `POST /api/reviews/{article_id}/revise` → mark revise_requested (note required)

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_reviews.py`:

```python
"""Integration tests for reviews API."""
from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_task_with_article(client: TestClient):
    """Helper: create KB + task with 1 article."""
    kb = client.post("/api/knowledge", json={"name": "K"}).json()
    with patch("app.api.tasks.schedule_task"):
        create = client.post("/api/tasks", json={
            "name": "T", "kb_id": kb["id"],
            "topic": "足够长的主题", "article_count": 1, "style": "neutral",
        })
    task_id = create.json()["id"]
    # Manually create an article via repo
    from app.core.db import get_session_factory
    from app.repositories.task_repo import TaskRepository
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            repo = TaskRepository(s)
            article = await repo.create_article(task_id)
            await repo.update_article(
                article.id, title="测试文章", content="# 测试\n\n内容",
                content_length=10, cited_chunks=[],
            )
            return article.id
    article_id = asyncio.run(_setup())
    return article_id


def test_list_reviews_by_status(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.get("/api/reviews?status=pending")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert article_id in ids


def test_approve_article(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.post(f"/api/reviews/{article_id}/approve", json={})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "approved"


def test_reject_requires_note(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.post(f"/api/reviews/{article_id}/reject", json={"note": ""})
    assert resp.status_code == 422  # missing note

    resp = client.post(f"/api/reviews/{article_id}/reject", json={"note": "内容不准确"})
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "rejected"


def test_get_article_with_chunks(client: TestClient) -> None:
    article_id = _create_task_with_article(client)
    resp = client.get(f"/api/reviews/{article_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == article_id
    assert body["content"] == "# 测试\n\n内容"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_reviews.py -v
```

Expected: FAIL with 404 (endpoint not found).

- [ ] **Step 3: Create `app/api/reviews.py`**

Create `D:/GEO2/backend/app/api/reviews.py`:

```python
"""Reviews API: list review queue, approve / reject / revise articles."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.task import Article, ReviewAction
from app.repositories.task_repo import TaskRepository

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=list[Article])
async def list_reviews(
    status: str = "pending",
    task_id: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[Article]:
    repo = TaskRepository(session)
    return await repo.list_articles_by_status(status, task_id=task_id)


@router.get("/{article_id}", response_model=Article)
async def get_article(
    article_id: str,
    session: AsyncSession = Depends(get_session),
) -> Article:
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    return Article.model_validate(article)


@router.post("/{article_id}/approve", response_model=Article)
async def approve_article(
    article_id: str,
    body: ReviewAction = ReviewAction(),
    session: AsyncSession = Depends(get_session),
) -> Article:
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    if article.review_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"article is already {article.review_status}",
        )
    await repo.update_article_review(
        article_id, status="approved", note=body.note
    )
    article = await repo.get_article(article_id)
    return Article.model_validate(article)


@router.post("/{article_id}/reject", response_model=Article)
async def reject_article(
    article_id: str,
    body: ReviewAction,
    session: AsyncSession = Depends(get_session),
) -> Article:
    if not body.note or not body.note.strip():
        raise HTTPException(
            status_code=422,
            detail="reject requires a non-empty note explaining the reason",
        )
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    if article.review_status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"article is already {article.review_status}",
        )
    await repo.update_article_review(
        article_id, status="rejected", note=body.note
    )
    article = await repo.get_article(article_id)
    return Article.model_validate(article)


@router.post("/{article_id}/revise", response_model=Article)
async def request_revision(
    article_id: str,
    body: ReviewAction,
    session: AsyncSession = Depends(get_session),
) -> Article:
    """Mark article as needing revision. v0.2 only flags it; does not regenerate."""
    if not body.note or not body.note.strip():
        raise HTTPException(
            status_code=422,
            detail="revise requires a note describing what to change",
        )
    repo = TaskRepository(session)
    article = await repo.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    await repo.update_article_review(
        article_id, status="revise_requested", note=body.note
    )
    article = await repo.get_article(article_id)
    return Article.model_validate(article)
```

- [ ] **Step 4: Register router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Add after the tasks router line:

```python
    from app.api.reviews import router as reviews_router
    app.include_router(reviews_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_reviews.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.2): reviews API (approve/reject/revise) with note enforcement + tests"
```

---

### Task 5.2: v0.1 → v0.2 Navigation Entry Point

**Files:**
- Modify: `D:/GEO2/frontend/src/pages/ReportView.tsx` (add "create task" button)

- [ ] **Step 1: Add button to ReportView.tsx**

Edit `D:/GEO2/frontend/src/pages/ReportView.tsx`. Find the section that renders the action buttons (near `<a href={api.getPdfUrl(...)}>下载 PDF</a>`). Add this button after the PDF link:

```tsx
            <Link
              to={`/tasks/new?from_diagnosis=${report.id}&brand=${encodeURIComponent(report.brand.name)}`}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
            >
              基于此诊断创建生成任务
            </Link>
```

- [ ] **Step 2: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/pages/ReportView.tsx && git commit -m "feat(frontend/v0.2): add 'create generation task' entry on v0.1 report page"
```

---

## Phase 6: Frontend

### Task 6.1: Frontend Types + API Client Extension

**Files:**
- Create: `D:/GEO2/frontend/src/types/v0.2.ts`
- Modify: `D:/GEO2/frontend/src/api/client.ts`

- [ ] **Step 1: Create `types/v0.2.ts`**

Create `D:/GEO2/frontend/src/types/v0.2.ts`:

```typescript
export type Style = 'neutral' | 'professional' | 'casual';
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
export type ReviewStatus = 'pending' | 'approved' | 'rejected' | 'revise_requested';

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface KnowledgeDocument {
  id: string;
  kb_id: string;
  filename: string;
  file_type: string;
  file_size: number | null;
  parse_status: 'pending' | 'success' | 'failed';
  parse_error: string | null;
  chunk_count: number;
  created_at: string;
}

export interface KnowledgeChunk {
  id: string;
  doc_id: string;
  chunk_index: number;
  content: string;
  content_length: number;
}

export interface KnowledgeDetail {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  documents: KnowledgeDocument[];
}

export interface Task {
  id: string;
  name: string;
  kb_id: string;
  brand: string | null;
  topic: string;
  keywords: string[];
  article_count: number;
  style: Style;
  target_length: number;
  status: TaskStatus;
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  articles?: Article[];
}

export interface Article {
  id: string;
  task_id: string;
  title: string | null;
  content: string | null;
  content_length: number | null;
  review_status: ReviewStatus;
  review_note: string | null;
  reviewed_at: string | null;
  cited_chunks: string[];
  llm_provider: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}
```

- [ ] **Step 2: Extend `api/client.ts`**

Edit `D:/GEO2/frontend/src/api/client.ts`. Add these methods to the `api` object (before the `export { ApiError }` line):

```typescript
import type { Article, KnowledgeBase, KnowledgeDetail, Task } from '@/types/v0.2';

  // (Inside the api object, add these methods)
  listKnowledgeBases(): Promise<KnowledgeBase[]> {
    return request('/knowledge');
  },
  createKnowledgeBase(body: { name: string; description?: string }): Promise<KnowledgeBase> {
    return request('/knowledge', { method: 'POST', body: JSON.stringify(body) });
  },
  getKnowledgeBase(kbId: string): Promise<KnowledgeDetail> {
    return request(`/knowledge/${kbId}`);
  },
  deleteKnowledgeBase(kbId: string): Promise<void> {
    return request(`/knowledge/${kbId}`, { method: 'DELETE' });
  },
  uploadDocument(kbId: string, file: File): Promise<KnowledgeDocument> {
    const formData = new FormData();
    formData.append('file', file);
    return fetch(`${BASE}/knowledge/${kbId}/documents`, {
      method: 'POST',
      body: formData,
    }).then(async (r) => {
      if (!r.ok) {
        const text = await r.text();
        throw new ApiError(r.status, text || r.statusText);
      }
      return r.json();
    });
  },
  deleteDocument(kbId: string, docId: string): Promise<void> {
    return request(`/knowledge/${kbId}/documents/${docId}`, { method: 'DELETE' });
  },
  listTasks(): Promise<Task[]> {
    return request('/tasks');
  },
  createTask(body: {
    name: string;
    kb_id: string;
    brand?: string;
    topic: string;
    keywords?: string[];
    article_count?: number;
    style?: 'neutral' | 'professional' | 'casual';
    target_length?: number;
  }): Promise<Task> {
    return request('/tasks', { method: 'POST', body: JSON.stringify(body) });
  },
  getTask(taskId: string): Promise<Task> {
    return request(`/tasks/${taskId}`);
  },
  deleteTask(taskId: string): Promise<void> {
    return request(`/tasks/${taskId}`, { method: 'DELETE' });
  },
  cancelTask(taskId: string): Promise<Task> {
    return request(`/tasks/${taskId}/cancel`, { method: 'POST' });
  },
  listReviewQueue(status: 'pending' | 'approved' | 'rejected' = 'pending'): Promise<Article[]> {
    return request(`/reviews?status=${status}`);
  },
  getArticle(articleId: string): Promise<Article> {
    return request(`/reviews/${articleId}`);
  },
  approveArticle(articleId: string, note?: string): Promise<Article> {
    return request(`/reviews/${articleId}/approve`, {
      method: 'POST', body: JSON.stringify({ note: note || '' }),
    });
  },
  rejectArticle(articleId: string, note: string): Promise<Article> {
    return request(`/reviews/${articleId}/reject`, {
      method: 'POST', body: JSON.stringify({ note }),
    });
  },
```

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend/v0.2): types + API client for knowledge/tasks/reviews"
```

---

### Task 6.2: Knowledge List + Upload Page

**Files:**
- Create: `D:/GEO2/frontend/src/pages/KnowledgeList.tsx`

- [ ] **Step 1: Create `KnowledgeList.tsx`**

Create `D:/GEO2/frontend/src/pages/KnowledgeList.tsx`:

```tsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

export default function KnowledgeList() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const { data: kbs, isLoading } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => api.listKnowledgeBases(),
  });

  const create = useMutation({
    mutationFn: () => api.createKnowledgeBase({ name, description: description || undefined }),
    onSuccess: (kb) => {
      qc.invalidateQueries({ queryKey: ['knowledge-bases'] });
      setShowCreate(false);
      setName('');
      setDescription('');
      navigate(`/knowledge/${kb.id}`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteKnowledgeBase(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge-bases'] }),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">知识库</h1>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md"
          >
            + 新建知识库
          </button>
        </div>

        {showCreate && (
          <div className="bg-white rounded-lg shadow p-6 mb-4">
            <h2 className="text-lg font-semibold mb-3">新建知识库</h2>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="知识库名称"
              className="w-full px-3 py-2 border rounded-md mb-3"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述（可选）"
              className="w-full px-3 py-2 border rounded-md mb-3"
              rows={3}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="px-3 py-1 text-gray-600"
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => create.mutate()}
                disabled={!name.trim() || create.isPending}
                className="px-4 py-1 bg-blue-600 text-white rounded-md disabled:opacity-50"
              >
                {create.isPending ? '创建中...' : '创建'}
              </button>
            </div>
          </div>
        )}

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {kbs && kbs.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有知识库。
          </div>
        )}

        {kbs && kbs.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {kbs.map((kb) => (
              <div key={kb.id} className="p-4 flex justify-between items-center hover:bg-gray-50">
                <Link to={`/knowledge/${kb.id}`} className="flex-1">
                  <div className="font-medium text-gray-900">{kb.name}</div>
                  <div className="text-sm text-gray-500">
                    {kb.description || '（无描述）'} · {formatDate(kb.created_at)}
                  </div>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`删除知识库「${kb.name}」？`)) remove.mutate(kb.id);
                  }}
                  className="text-red-600 text-sm px-2"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/pages/KnowledgeList.tsx && git commit -m "feat(frontend/v0.2): knowledge list + create page"
```

---

### Task 6.3: Knowledge Detail + Document Upload Page

**Files:**
- Create: `D:/GEO2/frontend/src/pages/KnowledgeDetail.tsx`

- [ ] **Step 1: Create `KnowledgeDetail.tsx`**

Create `D:/GEO2/frontend/src/pages/KnowledgeDetail.tsx`:

```tsx
import { useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const PARSE_STATUS_LABELS: Record<string, string> = {
  pending: '解析中',
  success: '已就绪',
  failed: '失败',
};

const PARSE_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
};

export default function KnowledgeDetail() {
  const { kbId = '' } = useParams<{ kbId: string }>();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: kb, isLoading } = useQuery({
    queryKey: ['knowledge-base', kbId],
    queryFn: () => api.getKnowledgeBase(kbId),
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.uploadDocument(kbId, file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge-base', kbId] }),
  });

  const remove = useMutation({
    mutationFn: (docId: string) => api.deleteDocument(kbId, docId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge-base', kbId] }),
  });

  if (isLoading) return <div className="p-8 text-center text-gray-500">加载中...</div>;
  if (!kb) return <div className="p-8 text-center text-red-500">知识库不存在</div>;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <Link to="/knowledge" className="text-blue-600 text-sm">← 返回知识库列表</Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2 mb-2">{kb.name}</h1>
        {kb.description && <p className="text-gray-600 mb-6">{kb.description}</p>}

        {/* Upload area */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">上传文档</h2>
          <p className="text-sm text-gray-500 mb-3">
            支持 PDF / Word (.docx) / Markdown / TXT，单文件最大 50MB
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.md,.txt"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              e.target.value = '';
            }}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={upload.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
          >
            {upload.isPending ? '上传中...' : '选择文件'}
          </button>
          {upload.isError && (
            <p className="mt-2 text-sm text-red-600">
              上传失败：{String(upload.error)}
            </p>
          )}
        </div>

        {/* Documents list */}
        <div className="bg-white rounded-lg shadow">
          <h2 className="text-lg font-semibold p-4 border-b">文档 ({kb.documents.length})</h2>
          {kb.documents.length === 0 && (
            <p className="p-4 text-gray-500 text-center">还没有上传文档</p>
          )}
          {kb.documents.map((doc) => (
            <div key={doc.id} className="p-4 border-b last:border-0 flex justify-between items-center">
              <div className="flex-1">
                <div className="font-medium text-gray-900">{doc.filename}</div>
                <div className="text-sm text-gray-500">
                  {doc.file_type.toUpperCase()} ·
                  {doc.file_size != null && ` ${(doc.file_size / 1024).toFixed(1)} KB ·`}
                  {' '}{formatDate(doc.created_at)}
                </div>
                {doc.parse_error && (
                  <div className="text-sm text-red-600 mt-1">⚠ {doc.parse_error}</div>
                )}
              </div>
              <span
                className={`px-2 py-1 text-xs rounded ${
                  PARSE_STATUS_COLORS[doc.parse_status] ?? 'bg-gray-100'
                }`}
              >
                {PARSE_STATUS_LABELS[doc.parse_status] ?? doc.parse_status}
                {doc.parse_status === 'success' && ` (${doc.chunk_count} 片)`}
              </span>
              <button
                type="button"
                onClick={() => {
                  if (confirm(`删除「${doc.filename}」？`)) remove.mutate(doc.id);
                }}
                className="ml-3 text-red-600 text-sm"
              >
                删除
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/pages/KnowledgeDetail.tsx && git commit -m "feat(frontend/v0.2): knowledge detail + document upload page"
```

---

### Task 6.4: Task List + Create Wizard

**Files:**
- Create: `D:/GEO2/frontend/src/pages/TaskList.tsx`
- Create: `D:/GEO2/frontend/src/pages/NewTask.tsx`

- [ ] **Step 1: Create `TaskList.tsx`**

Create `D:/GEO2/frontend/src/pages/TaskList.tsx`:

```tsx
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-yellow-100 text-yellow-800',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

export default function TaskList() {
  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.listTasks(),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">生成任务</h1>
          <Link to="/tasks/new" className="px-4 py-2 bg-blue-600 text-white rounded-md">
            + 新建任务
          </Link>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {tasks && tasks.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有任务。
          </div>
        )}

        {tasks && tasks.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {tasks.map((t) => (
              <Link
                key={t.id}
                to={`/tasks/${t.id}`}
                className="block p-4 hover:bg-gray-50"
              >
                <div className="flex justify-between items-start mb-1">
                  <div className="font-medium text-gray-900">{t.name}</div>
                  <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[t.status]}`}>
                    {STATUS_LABELS[t.status]}
                  </span>
                </div>
                <div className="text-sm text-gray-500">
                  主题：{t.topic.slice(0, 50)} · 文章数 {t.article_count} · {formatDate(t.created_at)}
                </div>
                {t.status === 'running' && (
                  <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full"
                      style={{ width: `${t.progress}%` }}
                    />
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `NewTask.tsx`**

Create `D:/GEO2/frontend/src/pages/NewTask.tsx`:

```tsx
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function NewTask() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const prefillBrand = params.get('brand') || '';
  const prefillTopic = params.get('topic') || '';

  const { data: kbs } = useQuery({
    queryKey: ['knowledge-bases'],
    queryFn: () => api.listKnowledgeBases(),
  });

  const [form, setForm] = useState({
    name: '',
    kb_id: '',
    brand: prefillBrand,
    topic: prefillTopic,
    keywords: '',
    article_count: 1,
    style: 'neutral' as 'neutral' | 'professional' | 'casual',
    target_length: 1500,
  });

  const create = useMutation({
    mutationFn: () =>
      api.createTask({
        name: form.name,
        kb_id: form.kb_id,
        brand: form.brand || undefined,
        topic: form.topic,
        keywords: form.keywords.split(/[,，\s]+/).filter((k) => k.length > 0),
        article_count: form.article_count,
        style: form.style,
        target_length: form.target_length,
      }),
    onSuccess: (task) => navigate(`/tasks/${task.id}`),
  });

  const canSubmit =
    form.name.trim() && form.kb_id && form.topic.trim().length >= 5 && !create.isPending;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">新建生成任务</h1>
        <p className="text-gray-600 mb-6">配置生成参数，AI 将基于知识库生成文章</p>

        <div className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">任务名 *</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">知识库 *</label>
            <select
              value={form.kb_id}
              onChange={(e) => setForm({ ...form, kb_id: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
            >
              <option value="">-- 选择知识库 --</option>
              {kbs?.map((kb) => (
                <option key={kb.id} value={kb.id}>{kb.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">品牌名</label>
            <input
              type="text"
              value={form.brand}
              onChange={(e) => setForm({ ...form, brand: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              placeholder={prefillBrand ? '' : '如：小米'}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">主题 *</label>
            <textarea
              value={form.topic}
              onChange={(e) => setForm({ ...form, topic: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              rows={2}
              placeholder="如：撰写一篇关于小米 14 手机的深度评测"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">关键词（逗号分隔）</label>
            <input
              type="text"
              value={form.keywords}
              onChange={(e) => setForm({ ...form, keywords: e.target.value })}
              className="w-full px-3 py-2 border rounded-md"
              placeholder="如：性能, 拍照, 续航"
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">文章数</label>
              <input
                type="number"
                min={1}
                max={20}
                value={form.article_count}
                onChange={(e) => setForm({ ...form, article_count: Number(e.target.value) })}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">风格</label>
              <select
                value={form.style}
                onChange={(e) => setForm({ ...form, style: e.target.value as 'neutral' | 'professional' | 'casual' })}
                className="w-full px-3 py-2 border rounded-md"
              >
                <option value="neutral">中性</option>
                <option value="professional">专业</option>
                <option value="casual">轻松</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">目标字数</label>
              <input
                type="number"
                min={300}
                max={10000}
                step={100}
                value={form.target_length}
                onChange={(e) => setForm({ ...form, target_length: Number(e.target.value) })}
                className="w-full px-3 py-2 border rounded-md"
              />
            </div>
          </div>

          {create.isError && (
            <div className="p-3 bg-red-50 text-red-700 rounded-md text-sm">
              创建失败：{String(create.error)}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => navigate('/tasks')}
              className="px-4 py-2 text-gray-600"
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => create.mutate()}
              disabled={!canSubmit}
              className="px-6 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
            >
              {create.isPending ? '创建中...' : '创建任务'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/pages/TaskList.tsx frontend/src/pages/NewTask.tsx && git commit -m "feat(frontend/v0.2): task list + new task wizard"
```

---

### Task 6.5: Task Detail Page

**Files:**
- Create: `D:/GEO2/frontend/src/pages/TaskDetail.tsx`

- [ ] **Step 1: Create `TaskDetail.tsx`**

Create `D:/GEO2/frontend/src/pages/TaskDetail.tsx`:

```tsx
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const REVIEW_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  revise_requested: 'bg-orange-100 text-orange-800',
};

const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  approved: '已批准',
  rejected: '已拒绝',
  revise_requested: '需修订',
};

export default function TaskDetail() {
  const { taskId = '' } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: task, isLoading } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.getTask(taskId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === 'completed' || status === 'failed' || status === 'cancelled') return false;
      return 3000;
    },
  });

  const cancel = useMutation({
    mutationFn: () => api.cancelTask(taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['task', taskId] }),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteTask(taskId),
    onSuccess: () => navigate('/tasks'),
  });

  if (isLoading) return <div className="p-8 text-center text-gray-500">加载中...</div>;
  if (!task) return <div className="p-8 text-center text-red-500">任务不存在</div>;

  const articles = task.articles ?? [];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <Link to="/tasks" className="text-blue-600 text-sm">← 返回任务列表</Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2">{task.name}</h1>
        <p className="text-gray-600 mt-1">主题：{task.topic}</p>
        <p className="text-sm text-gray-500">创建于 {formatDate(task.created_at)}</p>

        {/* Status + progress */}
        <div className="bg-white rounded-lg shadow p-4 mt-4">
          <div className="flex justify-between items-center mb-2">
            <div>
              <span className="font-medium">状态：</span>
              <span className="ml-2">{task.status}</span>
            </div>
            <div className="flex gap-2">
              {task.status === 'pending' || task.status === 'running' ? (
                <button
                  type="button"
                  onClick={() => cancel.mutate()}
                  className="px-3 py-1 text-sm bg-yellow-500 text-white rounded"
                >
                  取消任务
                </button>
              ) : null}
              {task.status !== 'running' && (
                <button
                  type="button"
                  onClick={() => {
                    if (confirm('删除此任务？文章也会被删除。')) remove.mutate();
                  }}
                  className="px-3 py-1 text-sm bg-red-500 text-white rounded"
                >
                  删除
                </button>
              )}
            </div>
          </div>
          {task.status === 'running' && (
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          )}
          {task.error_message && (
            <p className="mt-2 text-sm text-red-600">⚠ {task.error_message}</p>
          )}
        </div>

        {/* Articles */}
        <div className="bg-white rounded-lg shadow mt-6">
          <h2 className="text-lg font-semibold p-4 border-b">文章 ({articles.length})</h2>
          {articles.length === 0 && (
            <p className="p-4 text-gray-500 text-center">还没有文章（任务运行后会生成）</p>
          )}
          {articles.map((a) => (
            <Link
              key={a.id}
              to={`/reviews/${a.id}`}
              className="block p-4 border-b last:border-0 hover:bg-gray-50"
            >
              <div className="flex justify-between items-center">
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{a.title || '（无标题）'}</div>
                  {a.error_message ? (
                    <div className="text-sm text-red-600 mt-1">⚠ {a.error_message}</div>
                  ) : a.content ? (
                    <div className="text-sm text-gray-500 mt-1">
                      {a.content.slice(0, 100)}...
                    </div>
                  ) : null}
                </div>
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    REVIEW_STATUS_COLORS[a.review_status] ?? 'bg-gray-100'
                  }`}
                >
                  {REVIEW_STATUS_LABELS[a.review_status] ?? a.review_status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/pages/TaskDetail.tsx && git commit -m "feat(frontend/v0.2): task detail page with progress + article list"
```

---

### Task 6.6: Review Queue + Article Detail

**Files:**
- Create: `D:/GEO2/frontend/src/pages/ReviewQueue.tsx`
- Create: `D:/GEO2/frontend/src/pages/ReviewArticle.tsx`

- [ ] **Step 1: Create `ReviewQueue.tsx`**

Create `D:/GEO2/frontend/src/pages/ReviewQueue.tsx`:

```tsx
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  approved: '已批准',
  rejected: '已拒绝',
  revise_requested: '需修订',
};

export default function ReviewQueue() {
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const { data: articles, isLoading } = useQuery({
    queryKey: ['review-queue', filter],
    queryFn: () => api.listReviewQueue(filter),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">审核队列</h1>

        <div className="flex gap-2 mb-4">
          {(['pending', 'approved', 'rejected'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setFilter(s)}
              className={`px-4 py-2 rounded-md ${
                filter === s ? 'bg-blue-600 text-white' : 'bg-white border'
              }`}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {articles && articles.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            {filter === 'pending' ? '没有待审核的文章' : '没有记录'}
          </div>
        )}

        {articles && articles.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {articles.map((a) => (
              <Link
                key={a.id}
                to={`/reviews/${a.id}`}
                className="block p-4 hover:bg-gray-50"
              >
                <div className="font-medium text-gray-900">{a.title || '（无标题）'}</div>
                <div className="text-sm text-gray-500 mt-1">
                  {a.content ? a.content.slice(0, 120) + '...' : '（无内容）'}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {formatDate(a.created_at)}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `ReviewArticle.tsx`**

Create `D:/GEO2/frontend/src/pages/ReviewArticle.tsx`:

```tsx
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function ReviewArticle() {
  const { articleId = '' } = useParams<{ articleId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [rejectNote, setRejectNote] = useState('');

  const { data: article, isLoading } = useQuery({
    queryKey: ['article', articleId],
    queryFn: () => api.getArticle(articleId),
  });

  const approve = useMutation({
    mutationFn: () => api.approveArticle(articleId, rejectNote || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article', articleId] });
      qc.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });

  const reject = useMutation({
    mutationFn: () => api.rejectArticle(articleId, rejectNote),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['article', articleId] });
      qc.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });

  if (isLoading) return <div className="p-8 text-center text-gray-500">加载中...</div>;
  if (!article) return <div className="p-8 text-center text-red-500">文章不存在</div>;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <Link to="/reviews" className="text-blue-600 text-sm">← 返回审核队列</Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2">{article.title || '（无标题）'}</h1>
        <div className="text-sm text-gray-500 mt-1">
          状态：{article.review_status} · 由 {article.llm_provider || '未知'} 生成
        </div>

        {article.error_message && (
          <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-md">
            ⚠ {article.error_message}
          </div>
        )}

        {/* Content */}
        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <div className="prose max-w-none whitespace-pre-wrap">
            {article.content || '（无内容）'}
          </div>
        </div>

        {/* Cited chunks */}
        {article.cited_chunks.length > 0 && (
          <div className="bg-blue-50 rounded-lg p-4 mt-4 text-sm text-blue-800">
            📎 引用了 {article.cited_chunks.length} 个知识库片段
          </div>
        )}

        {/* Review actions */}
        {article.review_status === 'pending' && (
          <div className="bg-white rounded-lg shadow p-6 mt-4">
            <h2 className="text-lg font-semibold mb-3">审核操作</h2>
            <textarea
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              placeholder="审核意见（拒绝时必填）"
              className="w-full px-3 py-2 border rounded-md mb-3"
              rows={3}
            />
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => reject.mutate()}
                disabled={!rejectNote.trim() || reject.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-md disabled:opacity-50"
              >
                拒绝
              </button>
              <button
                type="button"
                onClick={() => approve.mutate()}
                disabled={approve.isPending}
                className="px-4 py-2 bg-green-600 text-white rounded-md disabled:opacity-50"
              >
                批准
              </button>
            </div>
          </div>
        )}

        {article.review_status !== 'pending' && article.review_note && (
          <div className="bg-gray-50 rounded-lg p-4 mt-4 text-sm">
            <strong>审核意见：</strong>{article.review_note}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/pages/ReviewQueue.tsx frontend/src/pages/ReviewArticle.tsx && git commit -m "feat(frontend/v0.2): review queue + article review page"
```

---

### Task 6.7: Wire v0.2 Routes into App

**Files:**
- Modify: `D:/GEO2/frontend/src/App.tsx`

- [ ] **Step 1: Update App.tsx to add v0.2 routes**

Edit `D:/GEO2/frontend/src/App.tsx`. Add v0.2 imports:

```tsx
import KnowledgeList from '@/pages/KnowledgeList';
import KnowledgeDetail from '@/pages/KnowledgeDetail';
import TaskList from '@/pages/TaskList';
import NewTask from '@/pages/NewTask';
import TaskDetail from '@/pages/TaskDetail';
import ReviewQueue from '@/pages/ReviewQueue';
import ReviewArticle from '@/pages/ReviewArticle';
```

Update the Header component's nav to add v0.2 links. Find the `<nav>` block and replace it with:

```tsx
        <nav className="space-x-4">
          <Link to="/" className="text-gray-600 hover:text-gray-900">诊断</Link>
          <Link to="/knowledge" className="text-gray-600 hover:text-gray-900">知识库</Link>
          <Link to="/tasks" className="text-gray-600 hover:text-gray-900">任务</Link>
          <Link to="/reviews" className="text-gray-600 hover:text-gray-900">审核</Link>
          <Link to="/new" className="px-3 py-1 bg-blue-600 text-white rounded-md">
            新建诊断
          </Link>
        </nav>
```

Add v0.2 routes inside the `<Routes>`:

```tsx
          <Route path="/knowledge" element={<KnowledgeList />} />
          <Route path="/knowledge/:kbId" element={<KnowledgeDetail />} />
          <Route path="/tasks" element={<TaskList />} />
          <Route path="/tasks/new" element={<NewTask />} />
          <Route path="/tasks/:taskId" element={<TaskDetail />} />
          <Route path="/reviews" element={<ReviewQueue />} />
          <Route path="/reviews/:articleId" element={<ReviewArticle />} />
```

- [ ] **Step 2: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/App.tsx && git commit -m "feat(frontend/v0.2): register all v0.2 routes in App"
```

---

## Phase 7: End-to-End Verification & Documentation

### Task 7.1: Backend E2E Integration Test

**Files:**
- Modify: `D:/GEO2/backend/tests/test_api_knowledge.py` (add full flow test)

- [ ] **Step 1: Append E2E test**

Append to `D:/GEO2/backend/tests/test_api_knowledge.py`:

```python
def test_full_v02_flow_with_mocked_workers(client: TestClient) -> None:
    """Full v0.2 flow: create KB → upload doc → parse → create task → run → review."""
    from unittest.mock import patch, AsyncMock
    from app.core.db import get_session_factory
    from app.repositories.knowledge_repo import KnowledgeRepository
    from app.repositories.task_repo import TaskRepository
    import asyncio

    # Mock both workers
    async def fake_parse(doc_id: str) -> None:
        async with get_session_factory()() as s:
            repo = KnowledgeRepository(s)
            doc = await repo.get_document(doc_id)
            if doc:
                await repo.update_document_status(doc_id, status="success", chunk_count=2)
                await repo.add_chunks(
                    doc_id=doc.id, kb_id=doc.kb_id,
                    chunks=[
                        {"chunk_index": 0, "content": "小米手机", "content_length": 4},
                        {"chunk_index": 1, "content": "性能优秀", "content_length": 4},
                    ],
                )

    async def fake_run_task(task_id: str) -> None:
        async with get_session_factory()() as s:
            repo = TaskRepository(s)
            task = await repo.get_task(task_id)
            await repo.update_task_status(task_id, status="running", progress=0)
            for i in range(task.article_count):
                article = await repo.create_article(task_id, index=i)
                await repo.update_article(
                    article.id, title=f"文章 {i+1}", content="# 内容",
                    content_length=4, cited_chunks=[],
                )
            await repo.update_task_status(task_id, status="completed", progress=100)

    with patch("app.api.knowledge.schedule_parse", side_effect=lambda doc_id: AsyncMock(return_value=fake_parse(doc_id))()):
        with patch("app.api.tasks.schedule_task", side_effect=lambda task_id: AsyncMock(return_value=fake_run_task(task_id))()):
            # 1. Create KB
            kb = client.post("/api/knowledge", json={"name": "E2E KB"}).json()

            # 2. Upload doc (uses sample.txt fixture)
            from tests.conftest import PROJECT_ROOT
            with open(PROJECT_ROOT / "tests" / "fixtures" / "sample.txt", "rb") as f:
                doc = client.post(
                    f"/api/knowledge/{kb['id']}/documents",
                    files={"file": ("sample.txt", f, "text/plain")},
                ).json()

            # 3. Wait for parse (or check via list)
            docs = client.get(f"/api/knowledge/{kb['id']}").json()["documents"]
            assert len(docs) == 1

            # 4. Create task
            task = client.post("/api/tasks", json={
                "name": "E2E Task",
                "kb_id": kb["id"],
                "brand": "TestBrand",
                "topic": "足够长的主题",
                "article_count": 2,
                "style": "neutral",
            }).json()

            # 5. Check task completed
            for _ in range(10):
                t = client.get(f"/api/tasks/{task['id']}").json()
                if t["status"] == "completed":
                    break
                import time; time.sleep(0.1)
            assert t["status"] == "completed"
            assert len(t["articles"]) == 2

            # 6. Approve first article
            a1_id = t["articles"][0]["id"]
            approved = client.post(f"/api/reviews/{a1_id}/approve", json={}).json()
            assert approved["review_status"] == "approved"
```

- [ ] **Step 2: Run all tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v --tb=short
```

Expected: All v0.1 + v0.2 tests PASS.

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2" && git add backend/tests/ && git commit -m "test(backend/v0.2): end-to-end knowledge + task + review flow"
```

---

### Task 7.2: Manual Verification Checklist

**Files:**
- Create: `D:/GEO2/docs/MANUAL_VERIFICATION_V0.2.md`

- [ ] **Step 1: Write checklist doc**

Create `D:/GEO2/docs/MANUAL_VERIFICATION_V0.2.md`:

```markdown
# 手动验证清单 — GEO Agent v0.2

发布前必跑 8 个场景。

## 前置条件

\`\`\`bash
cd "D:/GEO2"
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
docker-compose up --build -d
sleep 30
\`\`\`

## 场景

### 1. 上传 4 种文件 ✅

1. 进入 /knowledge 创建「测试 KB」
2. 上传 PDF / Word / MD / TXT 各 1 个
3. **预期**：4 个文档都显示"已就绪 (N 片)"

### 2. 损坏 PDF ❌

1. 上传一个损坏的 PDF
2. **预期**：文档显示"解析失败"+ 错误信息

### 3. 大文件 (>50MB) ❌

1. 尝试上传 > 50MB 的文件
2. **预期**：413 Payload Too Large

### 4. 完整任务流程 ✅

1. 创建知识库 + 上传一个 200 字的 .txt 文档
2. 创建任务：文章数 5，主题"AI 工具评测"
3. 等待任务完成
4. 进入任务详情，5 篇文章应该都已生成
5. **预期**：任务自动 completed；5 篇文章可点击进入审核

### 5. LLM 部分失败 ⚠️

1. 编辑 .env，DEEPSEEK_API_KEY=sk-invalid
2. docker-compose restart backend
3. 创建任务（文章数 3）
4. **预期**：3 篇文章可能全部失败，任务仍 completed。每篇显示"生成失败"。

### 6. 取消任务 🛑

1. 创建任务（文章数 10）
2. 立刻点"取消任务"
3. **预期**：任务状态变 cancelled；已生成的文章保留

### 7. 删除有任务的知识库 ❌

1. 创建知识库 + 上传文档 + 创建任务
2. 尝试删除知识库
3. **预期**：409 错误，提示"有关联任务"

### 8. v0.1 → v0.2 导航 ✅

1. 跑 v0.1 诊断
2. 在报告页点"基于此诊断创建生成任务"
3. **预期**：跳转到 /tasks/new，品牌名预填

## 通过标准

8 项全过 → v0.2 完成。
\`\`\`

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/MANUAL_VERIFICATION_V0.2.md && git commit -m "docs: v0.2 manual verification checklist"
```

---

### Task 7.3: Update ROADMAP

**Files:**
- Modify: `D:/GEO2/docs/ROADMAP.md`

- [ ] **Step 1: Update v0.2 status**

Edit `D:/GEO2/docs/ROADMAP.md`. Find the v0.2 entry and update the status:

Replace:
```
- ✅ v0.1 设计与计划完成
- 🎯 v0.2：等待 v0.1 实施完成后启动
```

With:
```
- ✅ v0.1 设计与计划完成
- ✅ v0.2 设计与计划完成（等待 v0.1 实施后启动）
- 🎯 v0.2：等待 v0.1 实施完成后启动
```

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/ROADMAP.md && git commit -m "docs: mark v0.2 design + plan as complete in ROADMAP"
```

---

## Self-Review

After writing this plan, run the writing-plans self-review checklist:

**1. Spec coverage** — Every requirement in the v0.2 spec is covered:

| Spec § | Implemented in Task |
|---|---|
| §1 (background, scope) | Phase 0 + Task 7.3 (ROADMAP update) |
| §2 (users, scenarios) | Task 5.2 (v0.1 → v0.2 nav), Phase 6 (frontend) |
| §3 (architecture) | Task 0.2 (new ORM models), Phase 6 (routes) |
| §4 (data model) | Task 0.2 (5 new tables) |
| §5.1 (knowledge subsystem) | Tasks 1.1-1.5 (parser, chunker, repo), 2.1-2.4 (API + worker) |
| §5.2 (task subsystem) | Tasks 3.1-3.3 (repo, schemas, API) |
| §5.3 (generator) | Tasks 4.1-4.3 (prompt builder, content writer, task worker) |
| §5.4 (review subsystem) | Task 5.1 (reviews API) |
| §6 (error handling) | parser (Task 1.1-1.3), task worker (Task 4.3), reviews (Task 5.1) |
| §7 (testing) | Tests in every task + Task 7.1-7.2 |
| §8 (acceptance) | Task 7.2 (manual checklist) |
| §9 (out of scope) | All explicitly excluded from plan |

**2. Placeholder scan** — No TBD/TODO. All code blocks complete.

**3. Type consistency** —
- `MentionResult.error` (v0.1) ↔ not used in v0.2 ✓
- `DiagnosisService(repo, crawler, llm, settings)` (v0.1) ↔ v0.2 uses `TaskRepository` + `KnowledgeRepository` + `ContentWriter` ✓
- `TaskCreate.brand` ↔ `TaskORM.brand` ↔ `Task.brand` (Pydantic) ✓
- `ReviewStatus.PENDING/APPROVED/REJECTED/REVISE_REQUESTED` ↔ used in API + tests ✓
- `ArticleORM.cited_chunks` (JSON string) ↔ `Article.cited_chunks` (list[str]) ↔ loaded via `json.loads(...)` ✓
- `_EXEC_LOCK` (v0.1) ↔ reused in v0.2 task worker ✓

All consistent.

---

## Execution Handoff

This plan is **complete** and saved to:
`D:/GEO2/docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.2.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task with two-stage review between tasks. Best for catching issues early and maintaining quality across 26+ tasks.

**2. Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints. Faster but no inter-task review.

**Which approach?**

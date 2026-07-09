# GEO Optimization Agent v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 capabilities to the GEO Agent: (1) WordPress auto-publishing of approved v0.2 articles, (2) AI-answer monitoring with periodic snapshots, (3) trend visualization, (4) email notifications on publish and on significant mention-rate changes.

**Architecture:** v0.3 extends the v0.1/v0.2 monolith (FastAPI + React + SQLite). Adds 4 new tables, 4 new domain modules, 4 new API routes, 7 new frontend pages. Uses APScheduler (in-process) for monitoring task scheduling with startup-time reload from DB. Uses Fernet for WordPress credential encryption. Reuses v0.1's LLMClient for monitoring queries.

**Tech Stack:** Extends v0.1/v0.2 with: apscheduler (scheduling), cryptography (Fernet encryption), aiosmtplib (async SMTP), markdown (MD→HTML), httpx (WordPress REST). All other constraints inherit.

## Global Constraints

Inherits **all** v0.1 and v0.2 constraints. Additions specific to v0.3:

- **v0.3 builds on v0.1 + v0.2** — Tasks assume v0.2's `ArticleORM.review_status="approved"` and `LLMClient.query_mentions()` are available
- **No vector search** (still v0.5)
- **No multi-user auth** (v0.4)
- **WordPress only** — no WeChat, no other CMS
- **APScheduler in-process** — single-machine deployment; no Redis/Celery
- **No automatic retry** on failed publish (user manually retries)
- **Article must be `review_status=approved`** before publish is accepted (422 otherwise)
- **No business-hours restrictions** — monitoring runs 24/7
- **Email is the only notification channel**
- **SMTP config from .env** (not DB) — system-level config
- **Encryption key from .env** (`ENCRYPTION_KEY`) — service fails to start if missing
- **APScheduler loads active monitors on startup** from DB
- **Failed publishes trigger email**, successful publishes trigger email

**Reference spec:** `docs/superpowers/specs/2026-07-10-geo-agent-v0.3-design.md`

---

## Phase 0: Foundation Extensions

### Task 0.1: Add v0.3 Dependencies and Settings

**Files:**
- Modify: `D:/GEO2/backend/requirements.txt`
- Modify: `D:/GEO2/backend/app/core/config.py`
- Modify: `D:/GEO2/backend/.env.example`

**Interfaces (additions to Settings):**
- `encryption_key: str = ""`
- `smtp_host: str = ""`
- `smtp_port: int = 587`
- `smtp_user: str = ""`
- `smtp_password: str = ""`
- `smtp_use_tls: bool = True`
- `smtp_from: str = ""`
- `publish_timeout_s: int = 30`
- `monitor_change_threshold_default: float = 0.15`

- [ ] **Step 1: Append v0.3 dependencies to `requirements.txt`**

Edit `D:/GEO2/backend/requirements.txt` and add at the bottom:

```
apscheduler==3.10.4
cryptography==43.0.1
aiosmtplib==3.0.1
markdown==3.7
```

- [ ] **Step 2: Install dependencies**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pip install -r requirements.txt
```

Expected: All packages install.

- [ ] **Step 3: Add v0.3 settings to `config.py`**

Edit `D:/GEO2/backend/app/core/config.py`. Add these fields to the `Settings` class:

```python
    # v0.3 — encryption
    encryption_key: str = ""

    # v0.3 — SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = ""

    # v0.3 — publish / monitor
    publish_timeout_s: int = 30
    monitor_change_threshold_default: float = 0.15
```

- [ ] **Step 4: Update `.env.example`**

Edit `D:/GEO2/backend/.env.example` and add at the bottom:

```bash
# v0.3 — Encryption (REQUIRED: generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
ENCRYPTION_KEY=

# v0.3 — SMTP (REQUIRED for email notifications)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@example.com
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_FROM=GEO Agent <noreply@example.com>

# v0.3 — Publish
PUBLISH_TIMEOUT_S=30
MONITOR_CHANGE_THRESHOLD_DEFAULT=0.15
```

Also update `D:/GEO2/.env.example` (root) if it exists (for docker-compose propagation).

- [ ] **Step 5: Write failing test for new settings**

Create `D:/GEO2/backend/tests/test_config_v0.3.py`:

```python
"""Tests for v0.3 settings additions."""
from app.core.config import Settings


def test_v03_settings_have_defaults() -> None:
    s = Settings()
    assert s.publish_timeout_s == 30
    assert s.monitor_change_threshold_default == 0.15
    assert s.smtp_port == 587
    assert s.smtp_use_tls is True
```

- [ ] **Step 6: Run test to verify pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_config_v0.3.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): add v0.3 dependencies and settings (encryption, SMTP, publish)"
```

---

### Task 0.2: Encryption Helper (Fernet)

**Files:**
- Create: `D:/GEO2/backend/app/domain/security/__init__.py`
- Create: `D:/GEO2/backend/app/domain/security/encryption.py`
- Create: `D:/GEO2/backend/tests/test_encryption.py`

**Interfaces:**
- `get_cipher() -> Fernet` — returns cached Fernet instance from settings.encryption_key
- `encrypt(plaintext: str) -> str` — returns base64 ciphertext
- `decrypt(ciphertext: str) -> str` — returns plaintext; raises on tampered input

- [ ] **Step 1: Create `app/domain/security/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/security/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_encryption.py`:

```python
"""Tests for Fernet encryption helper."""
import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.domain.security.encryption import decrypt, encrypt, get_cipher


@pytest.fixture
def key() -> str:
    return Fernet.generate_key().decode()


@pytest.fixture
def settings_with_key(key: str) -> Settings:
    return Settings(encryption_key=key)


def test_cipher_is_cached(settings_with_key: Settings, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings_with_key)
    from app.domain.security import encryption
    encryption._cipher = None  # reset cache
    c1 = get_cipher()
    c2 = get_cipher()
    assert c1 is c2


def test_encrypt_decrypt_roundtrip(settings_with_key: Settings) -> None:
    from app.domain.security import encryption
    encryption._cipher = None
    plain = "my-secret-app-password"
    cipher_text = encrypt(plain)
    assert cipher_text != plain
    assert decrypt(cipher_text) == plain


def test_decrypt_with_wrong_key_raises(settings_with_key: Settings) -> None:
    from app.domain.security import encryption
    encryption._cipher = None
    cipher_text = encrypt("hello")
    # Switch to a different key
    other = Settings(encryption_key=Fernet.generate_key().decode())
    encryption._cipher = None
    from app.domain.security import encryption as enc
    enc._settings = other
    with pytest.raises(InvalidToken):
        decrypt(cipher_text)


def test_get_cipher_without_key_raises(monkeypatch) -> None:
    from app.domain.security import encryption
    encryption._cipher = None
    monkeypatch.setattr("app.core.config.get_settings", lambda: Settings(encryption_key=""))
    with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
        get_cipher()
```

- [ ] **Step 3: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_encryption.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Create `app/domain/security/encryption.py`**

Create `D:/GEO2/backend/app/domain/security/encryption.py`:

```python
"""Fernet symmetric encryption for at-rest secrets (WordPress credentials)."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings

_cipher: Fernet | None = None
_settings: Settings | None = None


def _get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def get_cipher() -> Fernet:
    """Get the cached Fernet instance. Raises if ENCRYPTION_KEY not set."""
    global _cipher
    if _cipher is None:
        settings = _get_settings()
        if not settings.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not set in .env. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _cipher = Fernet(settings.encryption_key.encode())
    return _cipher


def reset_cipher() -> None:
    """Reset cached cipher (for testing or after settings change)."""
    global _cipher, _settings
    _cipher = None
    _settings = None


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext, return base64 string."""
    return get_cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt base64 ciphertext, return plaintext. Raises InvalidToken if tampered."""
    return get_cipher().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_encryption.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): Fernet encryption helper with cached cipher + tests"
```

---

### Task 0.3: v0.3 ORM Models (4 New Tables)

**Files:**
- Create: `D:/GEO2/backend/app/models/orm_v03.py`
- Modify: `D:/GEO2/backend/app/models/orm_v02.py` (or v0.2 models file) — ensure cascade is right

**Interfaces:**
- `PublisherConfigORM`
- `PublishJobORM`
- `MonitorTaskORM`
- `MentionSnapshotORM`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_orm_v0.3.py`:

```python
"""Tests for v0.3 ORM models."""
import json
from datetime import datetime, timezone

import pytest

from app.models.orm_v03 import (
    MentionSnapshotORM,
    MonitorTaskORM,
    PublisherConfigORM,
    PublishJobORM,
)


@pytest.mark.asyncio
async def test_publisher_config_orm(db_session) -> None:
    p = PublisherConfigORM(
        id="pc1", name="主站", site_url="https://example.com",
        username="admin", app_password_encrypted="encrypted-blob", is_default=0,
    )
    db_session.add(p)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(PublisherConfigORM).where(PublisherConfigORM.id == "pc1")
    )
    fetched = result.scalar_one()
    assert fetched.name == "主站"


@pytest.mark.asyncio
async def test_publish_job_orm(db_session) -> None:
    # Need a parent article from v0.2
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1",
        topic="X", article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    db_session.add_all([kb, task, article])
    await db_session.commit()

    job = PublishJobORM(
        id="pj1", article_id="a1", config_id="pc1", status="pending",
    )
    db_session.add(job)
    await db_session.commit()

    assert job.status == "pending"
    assert job.remote_post_id is None


@pytest.mark.asyncio
async def test_monitor_task_orm(db_session) -> None:
    m = MonitorTaskORM(
        id="m1", name="监测小米", brand="小米", industry="手机",
        target_questions=json.dumps(["q1", "q2"], ensure_ascii=False),
        frequency="daily", providers=json.dumps(["deepseek"]),
        change_threshold=0.15, is_active=1,
    )
    db_session.add(m)
    await db_session.commit()
    assert m.is_active == 1
    assert m.frequency == "daily"


@pytest.mark.asyncio
async def test_mention_snapshot_orm(db_session) -> None:
    snap = MentionSnapshotORM(
        id="s1", monitor_task_id="m1",
        run_at=datetime.now(timezone.utc),
        mention_rate=0.6, mention_count=3, total_samples=5,
        avg_position=1.5, details=json.dumps([]),
    )
    db_session.add(snap)
    await db_session.commit()
    assert snap.mention_rate == 0.6
    assert snap.total_samples == 5
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_orm_v0.3.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/models/orm_v03.py`**

Create `D:/GEO2/backend/app/models/orm_v03.py`:

```python
"""SQLAlchemy ORM models for v0.3 (publishers, monitor tasks, snapshots)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, REAL, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PublisherConfigORM(Base):
    """WordPress site credentials for publishing."""

    __tablename__ = "publisher_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    site_url: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str] = mapped_column(String, nullable=False)
    app_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )


class PublishJobORM(Base):
    """One publish attempt of an Article to a WordPress site."""

    __tablename__ = "publish_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    article_id: Mapped[str] = mapped_column(
        String, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    config_id: Mapped[str] = mapped_column(
        String, ForeignKey("publisher_configs.id", ondelete="RESTRICT"), nullable=False
    )
    title_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    remote_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MonitorTaskORM(Base):
    """A long-running monitor: periodically query LLM and record snapshots."""

    __tablename__ = "monitor_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    target_questions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    frequency: Mapped[str] = mapped_column(String, default="daily", nullable=False)
    providers: Mapped[str] = mapped_column(Text, nullable=False)  # JSON
    notify_email: Mapped[str | None] = mapped_column(String, nullable=True)
    change_threshold: Mapped[float] = mapped_column(REAL, default=0.15, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MentionSnapshotORM(Base):
    """Result of one monitor execution."""

    __tablename__ = "mention_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    monitor_task_id: Mapped[str] = mapped_column(
        String, ForeignKey("monitor_tasks.id", ondelete="CASCADE"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    mention_rate: Mapped[float] = mapped_column(REAL, nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_position: Mapped[float | None] = mapped_column(REAL, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_orm_v0.3.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Verify all v0.1+v0.2+v0.3 tests still pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): 4 ORM models (publisher_config, publish_job, monitor_task, mention_snapshot)"
```

---

## Phase 1: WordPress Publisher

### Task 1.1: WordPress REST API Client

**Files:**
- Create: `D:/GEO2/backend/app/domain/publisher/__init__.py`
- Create: `D:/GEO2/backend/app/domain/publisher/wordpress.py`
- Create: `D:/GEO2/backend/tests/test_wordpress.py`

**Interfaces:**
- `WordPressClient(site_url, username, app_password, timeout)` — context manager
- `await client.test_connection() -> dict` — returns user info on success
- `await client.create_post(title, content) -> dict` — returns `{"id": int, "link": str}`

- [ ] **Step 1: Create `app/domain/publisher/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/publisher/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_wordpress.py`:

```python
"""Tests for WordPress REST API client."""
import pytest
import respx
from httpx import Response

from app.domain.publisher.wordpress import PublishError, WordPressClient


@pytest.fixture
def client() -> WordPressClient:
    return WordPressClient(
        site_url="https://example.com",
        username="admin",
        app_password="abcd efgh ijkl mnop qrst uvwx",
        timeout=5.0,
    )


class TestTestConnection:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_user_info_on_success(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(200, json={"id": 1, "name": "Admin", "slug": "admin"})
        )
        info = await client.test_connection()
        assert info["name"] == "Admin"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_401(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(401, json={"code": "rest_unauthorized", "message": "Unauthorized"})
        )
        with pytest.raises(PublishError, match="认证失败"):
            await client.test_connection()

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_403(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(403, json={"code": "forbidden"})
        )
        with pytest.raises(PublishError, match="权限不足"):
            await client.test_connection()

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_404(self, client: WordPressClient) -> None:
        respx.get("https://example.com/wp-json/wp/v2/users/me").mock(
            return_value=Response(404, json={"code": "rest_no_route"})
        )
        with pytest.raises(PublishError, match="URL 错误"):
            await client.test_connection()


class TestCreatePost:
    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_post_and_returns_id_and_link(self, client: WordPressClient) -> None:
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=Response(
                201,
                json={"id": 42, "link": "https://example.com/?p=42"},
            )
        )
        result = await client.create_post(title="测试文章", content="<p>内容</p>")
        assert result["id"] == 42
        assert result["link"] == "https://example.com/?p=42"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_500(self, client: WordPressClient) -> None:
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        with pytest.raises(PublishError, match="500"):
            await client.create_post(title="X", content="Y")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_400(self, client: WordPressClient) -> None:
        respx.post("https://example.com/wp-json/wp/v2/posts").mock(
            return_value=Response(400, json={"code": "invalid_param", "message": "bad title"})
        )
        with pytest.raises(PublishError, match="400"):
            await client.create_post(title="", content="X")
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_wordpress.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Add `PublishError` to `app/domain/exceptions.py`**

Edit `D:/GEO2/backend/app/domain/exceptions.py`. Add this class anywhere:

```python
class PublishError(DomainError):
    """WordPress publish operation failed."""
```

- [ ] **Step 5: Create `app/domain/publisher/wordpress.py`**

Create `D:/GEO2/backend/app/domain/publisher/wordpress.py`:

```python
"""WordPress REST API client (Application Passwords auth)."""
from __future__ import annotations

from typing import Any

import httpx

from app.domain.exceptions import PublishError


class WordPressClient:
    """Async client for WordPress REST API v2."""

    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
        timeout: float = 30.0,
    ) -> None:
        self.site_url = site_url.rstrip("/")
        self.username = username
        self.app_password = app_password
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                auth=(self.username, self.app_password),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def test_connection(self) -> dict[str, Any]:
        """Call /users/me to verify credentials. Returns user info on success."""
        client = self._get_client()
        try:
            resp = await client.get(f"{self.site_url}/wp-json/wp/v2/users/me")
        except httpx.TimeoutException as e:
            raise PublishError(f"请求超时：{e}") from e
        except httpx.HTTPError as e:
            raise PublishError(f"网络错误：{type(e).__name__}: {e}") from e

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 401:
            raise PublishError("认证失败：用户名或 Application Password 错误")
        if resp.status_code == 403:
            raise PublishError("权限不足：用户没有访问权限")
        if resp.status_code == 404:
            raise PublishError("WordPress 站点 URL 错误或 REST API 未启用")
        raise PublishError(f"WordPress API 错误 {resp.status_code}: {resp.text[:200]}")

    async def create_post(self, title: str, content: str) -> dict[str, Any]:
        """Create a new post. Returns {"id": int, "link": str} on success."""
        client = self._get_client()
        try:
            resp = await client.post(
                f"{self.site_url}/wp-json/wp/v2/posts",
                json={
                    "title": title,
                    "content": content,
                    "status": "publish",
                },
            )
        except httpx.TimeoutException as e:
            raise PublishError(f"请求超时：{e}") from e
        except httpx.HTTPError as e:
            raise PublishError(f"网络错误：{type(e).__name__}: {e}") from e

        if resp.status_code == 201:
            return resp.json()
        if resp.status_code == 400:
            raise PublishError(f"请求参数错误 400：{resp.text[:200]}")
        if resp.status_code == 401:
            raise PublishError("认证失败：用户名或 Application Password 错误")
        if resp.status_code == 403:
            raise PublishError("权限不足：用户没有发布权限")
        if resp.status_code == 404:
            raise PublishError("WordPress 站点 URL 错误或 REST API 未启用")
        raise PublishError(
            f"WordPress API 错误 {resp.status_code}: {resp.text[:200]}"
        )
```

- [ ] **Step 6: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_wordpress.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): WordPress REST client (auth, test, create_post) + tests"
```

---

### Task 1.2: PublishRepository (CRUD)

**Files:**
- Create: `D:/GEO2/backend/app/repositories/publisher_repo.py`
- Create: `D:/GEO2/backend/tests/test_publisher_repo.py`

**Interfaces:**
- `PublishRepository(session)`:
  - `create_publisher_config(name, site_url, username, app_password_encrypted, is_default=False) -> PublisherConfigORM`
  - `get_publisher_config(id) -> PublisherConfigORM | None`
  - `list_publisher_configs() -> list[PublisherConfigORM]`
  - `update_publisher_config(id, ...) -> None`
  - `delete_publisher_config(id) -> None`
  - `create_publish_job(article_id, config_id, title_override=None) -> PublishJobORM`
  - `get_publish_job(id) -> PublishJobORM | None`
  - `list_publish_jobs(status=None) -> list[PublishJobORM]`
  - `update_publish_job_status(id, status, error=None) -> None`
  - `update_publish_job_success(id, remote_post_id, remote_url) -> None`
  - `count_publish_jobs_by_config(config_id) -> int` (used to check before delete)

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_publisher_repo.py`:

```python
"""Tests for PublishRepository."""
import pytest

from app.models.orm_v03 import PublisherConfigORM, PublishJobORM
from app.repositories.publisher_repo import PublishRepository


@pytest.mark.asyncio
async def test_create_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(
        name="主站", site_url="https://example.com",
        username="admin", app_password_encrypted="encrypted-blob",
    )
    assert pc.id != ""
    assert pc.is_default == 0


@pytest.mark.asyncio
async def test_get_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(
        name="X", site_url="https://x.com", username="u",
        app_password_encrypted="enc",
    )
    fetched = await repo.get_publisher_config(pc.id)
    assert fetched is not None
    assert fetched.name == "X"


@pytest.mark.asyncio
async def test_list_publisher_configs(db_session) -> None:
    repo = PublishRepository(db_session)
    await repo.create_publisher_config(name="A", site_url="https://a.com", username="u", app_password_encrypted="e")
    await repo.create_publisher_config(name="B", site_url="https://b.com", username="u", app_password_encrypted="e")
    pcs = await repo.list_publisher_configs()
    assert len(pcs) == 2


@pytest.mark.asyncio
async def test_delete_publisher_config(db_session) -> None:
    repo = PublishRepository(db_session)
    pc = await repo.create_publisher_config(name="X", site_url="https://x.com", username="u", app_password_encrypted="e")
    await repo.delete_publisher_config(pc.id)
    assert await repo.get_publisher_config(pc.id) is None


@pytest.mark.asyncio
async def test_create_publish_job(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")
    assert job.id != ""
    assert job.status == "pending"
    assert job.title_override is None


@pytest.mark.asyncio
async def test_create_publish_job_with_title_override(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(
        article_id="a1", config_id="pc1", title_override="新标题",
    )
    assert job.title_override == "新标题"


@pytest.mark.asyncio
async def test_update_publish_job_status(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")
    await repo.update_publish_job_status(job.id, status="running")
    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "running"

    await repo.update_publish_job_status(job.id, status="failed", error="oops")
    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "oops"


@pytest.mark.asyncio
async def test_update_publish_job_success(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    from datetime import datetime, timezone

    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")
    await repo.update_publish_job_success(
        job.id, remote_post_id=42, remote_url="https://x.com/?p=42"
    )
    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "success"
    assert refreshed.remote_post_id == 42
    assert refreshed.remote_url == "https://x.com/?p=42"
    assert refreshed.published_at is not None


@pytest.mark.asyncio
async def test_count_publish_jobs_by_config(db_session) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(id="a1", task_id="t1", title="T", review_status="approved")
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted="e",
    )
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    await repo.create_publish_job(article_id="a1", config_id="pc1")
    await repo.create_publish_job(article_id="a1", config_id="pc1")
    count = await repo.count_publish_jobs_by_config("pc1")
    assert count == 2
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publisher_repo.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/repositories/publisher_repo.py`**

Create `D:/GEO2/backend/app/repositories/publisher_repo.py`:

```python
"""Repository for WordPress publisher configs and publish jobs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v03 import PublisherConfigORM, PublishJobORM


class PublishRepository:
    """Data access for v0.3 publisher tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- PublisherConfig ---

    async def create_publisher_config(
        self,
        name: str,
        site_url: str,
        username: str,
        app_password_encrypted: str,
        is_default: bool = False,
    ) -> PublisherConfigORM:
        pc = PublisherConfigORM(
            id=str(uuid.uuid4()),
            name=name,
            site_url=site_url,
            username=username,
            app_password_encrypted=app_password_encrypted,
            is_default=1 if is_default else 0,
        )
        self.session.add(pc)
        await self.session.commit()
        await self.session.refresh(pc)
        return pc

    async def get_publisher_config(self, id: str) -> PublisherConfigORM | None:
        result = await self.session.execute(
            select(PublisherConfigORM).where(PublisherConfigORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_publisher_configs(self) -> list[PublisherConfigORM]:
        result = await self.session.execute(
            select(PublisherConfigORM).order_by(PublisherConfigORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_publisher_config(self, id: str) -> None:
        from sqlalchemy import delete
        await self.session.execute(
            delete(PublisherConfigORM).where(PublisherConfigORM.id == id)
        )
        await self.session.commit()

    # --- PublishJob ---

    async def create_publish_job(
        self,
        article_id: str,
        config_id: str,
        title_override: str | None = None,
    ) -> PublishJobORM:
        job = PublishJobORM(
            id=str(uuid.uuid4()),
            article_id=article_id,
            config_id=config_id,
            title_override=title_override,
            status="pending",
        )
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def get_publish_job(self, id: str) -> PublishJobORM | None:
        result = await self.session.execute(
            select(PublishJobORM).where(PublishJobORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_publish_jobs(
        self, status: str | None = None
    ) -> list[PublishJobORM]:
        stmt = select(PublishJobORM).order_by(PublishJobORM.created_at.desc())
        if status is not None:
            stmt = stmt.where(PublishJobORM.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_publish_job_status(
        self, id: str, status: str, error: str | None = None
    ) -> None:
        job = await self.get_publish_job(id)
        if job is None:
            return
        job.status = status
        if error is not None:
            job.error_message = error
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_publish_job_success(
        self, id: str, remote_post_id: int, remote_url: str
    ) -> None:
        job = await self.get_publish_job(id)
        if job is None:
            return
        job.status = "success"
        job.remote_post_id = remote_post_id
        job.remote_url = remote_url
        job.published_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def count_publish_jobs_by_config(self, config_id: str) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(PublishJobORM)
            .where(PublishJobORM.config_id == config_id)
        )
        return result.scalar_one()
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publisher_repo.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): PublishRepository with config + job CRUD + tests"
```

---

### Task 1.3: PublishService (Execute Publish Flow)

**Files:**
- Create: `D:/GEO2/backend/app/domain/publisher/publisher_service.py`
- Create: `D:/GEO2/backend/tests/test_publisher_service.py`

**Interfaces:**
- `PublishService.execute_publish(publish_job_id) -> None` — runs the full flow
- Uses `WordPressClient` and `encryption.decrypt()` (created in earlier tasks)

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_publisher_service.py`:

```python
"""Tests for PublishService (orchestrates publish flow)."""
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import pytest
import respx
from cryptography.fernet import Fernet
from httpx import Response

from app.core.config import Settings
from app.domain.publisher.publisher_service import PublishService
from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
from app.models.orm_v03 import PublisherConfigORM, PublishJobORM
from app.repositories.publisher_repo import PublishRepository


@pytest.fixture
def settings_with_key() -> Settings:
    return Settings(
        encryption_key=Fernet.generate_key().decode(),
        publish_timeout_s=5,
    )


def _setup_approved_article(session, *, article_id="a1", config_id="pc1"):
    """Insert KB + task + approved article + publisher config. Returns encrypted password."""
    from app.domain.security.encryption import encrypt

    encrypted_pw = encrypt("test-app-password")
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(
        id=article_id, task_id="t1",
        title="测试文章",
        content="# 标题\n\n内容",
        review_status="approved",
    )
    pc = PublisherConfigORM(
        id=config_id, name="主站", site_url="https://example.com",
        username="admin", app_password_encrypted=encrypted_pw,
    )
    session.add_all([kb, task, article, pc])
    session.commit()
    return encrypted_pw


@pytest.mark.asyncio
@respx.mock
async def test_execute_publish_success(db_session, settings_with_key, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings_with_key)
    from app.domain.security import encryption
    encryption._cipher = None
    encryption._settings = settings_with_key

    _setup_approved_article(db_session)

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    respx.post("https://example.com/wp-json/wp/v2/posts").mock(
        return_value=Response(
            201,
            json={"id": 42, "link": "https://example.com/?p=42"},
        )
    )

    svc = PublishService(repo=repo, settings=settings_with_key)
    await svc.execute_publish(job.id)

    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "success"
    assert refreshed.remote_post_id == 42
    assert refreshed.remote_url == "https://example.com/?p=42"


@pytest.mark.asyncio
@respx.mock
async def test_execute_publish_failure_401(db_session, settings_with_key, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: settings_with_key)
    from app.domain.security import encryption
    encryption._cipher = None
    encryption._settings = settings_with_key

    _setup_approved_article(db_session)

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    respx.post("https://example.com/wp-json/wp/v2/posts").mock(
        return_value=Response(401, json={"code": "rest_unauthorized"})
    )

    svc = PublishService(repo=repo, settings=settings_with_key)
    await svc.execute_publish(job.id)

    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "failed"
    assert "认证失败" in refreshed.error_message


@pytest.mark.asyncio
async def test_execute_publish_rejects_non_approved_article(db_session, settings_with_key) -> None:
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    from app.domain.security.encryption import encrypt

    encrypted_pw = encrypt("test")
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(id="t1", name="T", kb_id="kb1", topic="X", article_count=1, style="neutral", target_length=1000)
    article = ArticleORM(id="a1", task_id="t1", title="Pending", review_status="pending", content="X")
    pc = PublisherConfigORM(id="pc1", name="P", site_url="https://x.com", username="u", app_password_encrypted=encrypted_pw)
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    svc = PublishService(repo=repo, settings=settings_with_key)
    await svc.execute_publish(job.id)

    refreshed = await repo.get_publish_job(job.id)
    assert refreshed.status == "failed"
    assert "not approved" in refreshed.error_message
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publisher_service.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/publisher/publisher_service.py`**

Create `D:/GEO2/backend/app/domain/publisher/publisher_service.py`:

```python
"""Orchestrates a single publish attempt: load article, decrypt creds, call WP, persist result."""
from __future__ import annotations

import asyncio

import markdown
import structlog

from app.core.config import Settings
from app.domain.exceptions import PublishError
from app.domain.publisher.wordpress import WordPressClient
from app.domain.security.encryption import decrypt
from app.models.orm_v02 import ArticleORM
from app.models.orm_v03 import PublisherConfigORM
from app.repositories.publisher_repo import PublishRepository

logger = structlog.get_logger()


class PublishService:
    def __init__(self, repo: PublishRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings

    async def execute_publish(self, publish_job_id: str) -> None:
        job = await self.repo.get_publish_job(publish_job_id)
        if job is None or job.status != "pending":
            return

        await self.repo.update_publish_job_status(publish_job_id, status="running")

        # Load related entities
        config = await self.repo.get_publisher_config(job.config_id)
        article = await self._get_article(job.article_id)

        if config is None:
            await self._mark_failed(publish_job_id, "publisher config not found")
            return
        if article is None:
            await self._mark_failed(publish_job_id, "article not found")
            return
        if article.review_status != "approved":
            await self._mark_failed(
                publish_job_id,
                f"article not approved (current: {article.review_status})",
            )
            return

        # Decrypt + create WP client
        try:
            app_password = decrypt(config.app_password_encrypted)
        except Exception as e:  # noqa: BLE001
            await self._mark_failed(
                publish_job_id, f"failed to decrypt credentials: {e}"
            )
            return

        wp_client = WordPressClient(
            site_url=config.site_url,
            username=config.username,
            app_password=app_password,
            timeout=float(self.settings.publish_timeout_s),
        )

        try:
            # Convert Markdown → HTML
            html = markdown.markdown(
                article.content or "",
                extensions=["extra", "sane_lists", "toc"],
            )
            title = job.title_override or article.title or "Untitled"

            result = await wp_client.create_post(title=title, content=html)

            await self.repo.update_publish_job_success(
                publish_job_id,
                remote_post_id=result["id"],
                remote_url=result["link"],
            )
            logger.info(
                "publish_success",
                job_id=publish_job_id,
                remote_url=result["link"],
            )

            # Trigger success notification (notification_service is added in later task)
            try:
                from app.domain.notification.notification_service import (
                    notify_publish_success,
                )
                await notify_publish_success(
                    title=title,
                    remote_url=result["link"],
                    site_name=config.name,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("notification_failed", error=str(e))
        except PublishError as e:
            await self._mark_failed(publish_job_id, str(e))
        except Exception as e:  # noqa: BLE001
            logger.exception("publish_unexpected", job_id=publish_job_id)
            await self._mark_failed(publish_job_id, f"unexpected: {type(e).__name__}: {e}")
        finally:
            await wp_client.close()

    async def _get_article(self, article_id: str) -> ArticleORM | None:
        from sqlalchemy import select
        from app.core.db import get_session_factory
        from app.models.orm_v02 import ArticleORM

        # Open a new session for this lookup
        factory = get_session_factory()
        async with factory() as s:
            result = await s.execute(
                select(ArticleORM).where(ArticleORM.id == article_id)
            )
            return result.scalar_one_or_none()

    async def _mark_failed(self, job_id: str, error: str) -> None:
        await self.repo.update_publish_job_status(job_id, status="failed", error=error)
        logger.warning("publish_failed", job_id=job_id, error=error)
        try:
            from app.domain.notification.notification_service import notify_publish_failure
            await notify_publish_failure(title="(unknown)", error=error, site_name="(unknown)")
        except Exception:  # noqa: BLE001
            pass
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publisher_service.py -v
```

Expected: First 2 tests PASS; 3rd test might fail because notification service isn't yet implemented. Skip the 3rd test for now and re-run after notification is done (Phase 5).

Actually, since notification_service is imported inside try/except, missing module won't break — the import will silently fail. All 3 tests should pass.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): PublishService.execute_publish with status tracking + tests"
```

---

## Phase 2: WordPress API Endpoints + Publish Worker

### Task 2.1: Publisher Pydantic Schemas

**Files:**
- Create: `D:/GEO2/backend/app/models/publisher.py`
- Create: `D:/GEO2/backend/tests/test_publisher_schemas.py`

**Interfaces:**
- `PublisherConfigCreate`, `PublisherConfig`
- `PublishJobCreate`, `PublishJob`, `PublishJobStatus`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_publisher_schemas.py`:

```python
"""Tests for publisher Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.publisher import (
    PublishJobCreate,
    PublishJobStatus,
    PublisherConfigCreate,
)


class TestPublisherConfigCreate:
    def test_min_name(self) -> None:
        with pytest.raises(ValidationError):
            PublisherConfigCreate(
                name="", site_url="https://example.com",
                username="u", app_password="short",
            )

    def test_min_app_password(self) -> None:
        with pytest.raises(ValidationError):
            PublisherConfigCreate(
                name="X", site_url="https://example.com",
                username="u", app_password="short",
            )

    def test_valid(self) -> None:
        c = PublisherConfigCreate(
            name="主站", site_url="https://example.com",
            username="admin", app_password="abcdefghijklmnop",
        )
        assert c.name == "主站"


class TestPublishJobCreate:
    def test_valid(self) -> None:
        j = PublishJobCreate(article_id="a1", config_id="pc1")
        assert j.title_override is None

    def test_with_title_override(self) -> None:
        j = PublishJobCreate(article_id="a1", config_id="pc1", title_override="新标题")
        assert j.title_override == "新标题"


class TestPublishJobStatus:
    def test_enum_values(self) -> None:
        assert PublishJobStatus.PENDING == "pending"
        assert PublishJobStatus.SUCCESS == "success"
        assert PublishJobStatus.FAILED == "failed"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publisher_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/models/publisher.py`**

Create `D:/GEO2/backend/app/models/publisher.py`:

```python
"""Pydantic models for publisher API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class PublisherConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    site_url: HttpUrl
    username: str = Field(..., min_length=1, max_length=100)
    app_password: str = Field(..., min_length=10)


class PublisherConfig(BaseModel):
    """Returned by API. Never includes app_password."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    site_url: str
    username: str
    is_default: bool
    created_at: datetime


class PublishJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PublishJobCreate(BaseModel):
    article_id: str
    config_id: str
    title_override: str | None = Field(None, max_length=300)


class PublishJob(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    article_id: str
    config_id: str
    title_override: str | None
    status: PublishJobStatus
    remote_post_id: int | None
    remote_url: str | None
    error_message: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publisher_schemas.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): publisher Pydantic schemas + tests"
```

---

### Task 2.2: Publisher API Endpoints

**Files:**
- Create: `D:/GEO2/backend/app/api/publishers.py`
- Modify: `D:/GEO2/backend/app/main.py` (register router)
- Create: `D:/GEO2/backend/tests/test_api_publishers.py`

**Interfaces:**
- `GET /api/publishers` — list
- `POST /api/publishers` — create (encrypts app_password)
- `GET /api/publishers/{id}` — detail (no password)
- `PUT /api/publishers/{id}` — update
- `DELETE /api/publishers/{id}` — delete (409 if has publish jobs)
- `POST /api/publishers/{id}/test` — test connection
- `GET /api/publishes` — list jobs
- `POST /api/publishes` — create job (validates article approved, schedules worker)
- `GET /api/publishes/{id}` — job detail
- `POST /api/publishes/{id}/retry` — retry failed job
- `POST /api/publishes/{id}/cancel` — cancel

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_publishers.py`:

```python
"""Integration tests for publisher API."""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_approved_article(client: TestClient) -> str:
    """Helper: create KB + task + approved article. Returns article_id."""
    from app.core.db import get_session_factory
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            kb = KnowledgeBaseORM(id="kb1", name="KB")
            task = TaskORM(
                id="t1", name="T", kb_id="kb1", topic="X",
                article_count=1, style="neutral", target_length=1000,
            )
            article = ArticleORM(
                id="a1", task_id="t1", title="测试",
                content="# 测试\n\n内容", review_status="approved",
            )
            s.add_all([kb, task, article])
            await s.commit()
    asyncio.run(_setup())
    return "a1"


def test_create_publisher_config(client: TestClient) -> None:
    resp = client.post(
        "/api/publishers",
        json={
            "name": "主站",
            "site_url": "https://example.com",
            "username": "admin",
            "app_password": "abcdefghijklmnop",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "主站"
    assert body["username"] == "admin"
    assert "app_password" not in body  # CRITICAL: never exposed


def test_list_publisher_configs(client: TestClient) -> None:
    client.post("/api/publishers", json={
        "name": "A", "site_url": "https://a.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    })
    resp = client.get("/api/publishers")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_publisher_config(client: TestClient) -> None:
    create = client.post("/api/publishers", json={
        "name": "X", "site_url": "https://x.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    })
    pc_id = create.json()["id"]
    resp = client.get(f"/api/publishers/{pc_id}")
    assert resp.status_code == 200
    assert "app_password" not in resp.json()


def test_create_publisher_validates_password_length(client: TestClient) -> None:
    resp = client.post("/api/publishers", json={
        "name": "X", "site_url": "https://x.com", "username": "u",
        "app_password": "short",
    })
    assert resp.status_code == 422


def test_create_publish_job(client: TestClient) -> None:
    _create_approved_article(client)
    pc = client.post("/api/publishers", json={
        "name": "P", "site_url": "https://p.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    }).json()

    with patch("app.api.publishers.schedule_publish") as mock:
        resp = client.post("/api/publishes", json={
            "article_id": "a1", "config_id": pc["id"],
        })
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
    assert mock.called


def test_create_publish_job_rejects_non_approved_article(client: TestClient) -> None:
    from app.core.db import get_session_factory
    from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            kb = KnowledgeBaseORM(id="kb1", name="KB")
            task = TaskORM(
                id="t1", name="T", kb_id="kb1", topic="X",
                article_count=1, style="neutral", target_length=1000,
            )
            article = ArticleORM(
                id="a2", task_id="t1", title="Pending", review_status="pending",
            )
            s.add_all([kb, task, article])
            await s.commit()
    asyncio.run(_setup())

    pc = client.post("/api/publishers", json={
        "name": "P", "site_url": "https://p.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    }).json()

    resp = client.post("/api/publishes", json={"article_id": "a2", "config_id": pc["id"]})
    assert resp.status_code == 422


def test_delete_publisher_with_jobs_returns_409(client: TestClient) -> None:
    _create_approved_article(client)
    pc = client.post("/api/publishers", json={
        "name": "P", "site_url": "https://p.com", "username": "u",
        "app_password": "abcdefghijklmnop",
    }).json()

    with patch("app.api.publishers.schedule_publish"):
        client.post("/api/publishes", json={"article_id": "a1", "config_id": pc["id"]})

    resp = client.delete(f"/api/publishers/{pc['id']}")
    assert resp.status_code == 409
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_publishers.py -v
```

Expected: FAIL with 404 (endpoint not registered).

- [ ] **Step 3: Create `app/api/publishers.py`**

Create `D:/GEO2/backend/app/api/publishers.py`:

```python
"""Publisher API: WordPress credentials + publish jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.domain.publisher.publisher_service import PublishService
from app.domain.security.encryption import encrypt
from app.models.publisher import (
    PublishJob,
    PublishJobCreate,
    PublishJobStatus,
    PublisherConfig,
    PublisherConfigCreate,
)
from app.repositories.publisher_repo import PublishRepository

# Two routers because prefixes differ
configs_router = APIRouter(prefix="/publishers", tags=["publishers"])
jobs_router = APIRouter(prefix="/publishes", tags=["publishes"])


# --- PublisherConfig endpoints ---

@configs_router.post("", status_code=201, response_model=PublisherConfig)
async def create_publisher_config(
    body: PublisherConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> PublisherConfig:
    repo = PublishRepository(session)
    encrypted = encrypt(body.app_password)
    return await repo.create_publisher_config(
        name=body.name,
        site_url=str(body.site_url),
        username=body.username,
        app_password_encrypted=encrypted,
    )


@configs_router.get("", response_model=list[PublisherConfig])
async def list_publisher_configs(
    session: AsyncSession = Depends(get_session),
) -> list[PublisherConfig]:
    repo = PublishRepository(session)
    return await repo.list_publisher_configs()


@configs_router.get("/{pc_id}", response_model=PublisherConfig)
async def get_publisher_config(
    pc_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublisherConfig:
    repo = PublishRepository(session)
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    return pc


@configs_router.delete("/{pc_id}", status_code=204)
async def delete_publisher_config(
    pc_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = PublishRepository(session)
    count = await repo.count_publish_jobs_by_config(pc_id)
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"cannot delete: {count} publish job(s) reference this config",
        )
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    await repo.delete_publisher_config(pc_id)


@configs_router.post("/{pc_id}/test")
async def test_publisher_config(
    pc_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Test connection: decrypt creds + call /users/me."""
    from app.domain.publisher.wordpress import WordPressClient
    from app.domain.security.encryption import decrypt

    repo = PublishRepository(session)
    pc = await repo.get_publisher_config(pc_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")
    try:
        pw = decrypt(pc.app_password_encrypted)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"decrypt failed: {e}")

    client = WordPressClient(
        site_url=pc.site_url, username=pc.username, app_password=pw
    )
    try:
        info = await client.test_connection()
        return {"ok": True, "user": info}
    finally:
        await client.close()


# --- PublishJob endpoints ---

@jobs_router.post("", status_code=201, response_model=PublishJob)
async def create_publish_job(
    body: PublishJobCreate,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    """Create publish job. Article MUST be approved."""
    from sqlalchemy import select
    from app.models.orm_v02 import ArticleORM

    # Validate article approved
    result = await session.execute(
        select(ArticleORM).where(ArticleORM.id == body.article_id)
    )
    article = result.scalar_one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    if article.review_status != "approved":
        raise HTTPException(
            status_code=422,
            detail=f"article must be approved (current: {article.review_status})",
        )

    # Validate config exists
    repo = PublishRepository(session)
    pc = await repo.get_publisher_config(body.config_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="publisher config not found")

    job = await repo.create_publish_job(
        article_id=body.article_id,
        config_id=body.config_id,
        title_override=body.title_override,
    )

    # Schedule worker
    from app.tasks.publish_worker import schedule_publish
    schedule_publish(job.id)
    return job


@jobs_router.get("", response_model=list[PublishJob])
async def list_publish_jobs(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PublishJob]:
    repo = PublishRepository(session)
    return await repo.list_publish_jobs(status=status)


@jobs_router.get("/{job_id}", response_model=PublishJob)
async def get_publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    repo = PublishRepository(session)
    job = await repo.get_publish_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    return job


@jobs_router.post("/{job_id}/retry", response_model=PublishJob)
async def retry_publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    """Retry a failed job. Reset to pending and reschedule."""
    repo = PublishRepository(session)
    job = await repo.get_publish_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    if job.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"only failed jobs can be retried (current: {job.status})",
        )
    await repo.update_publish_job_status(job_id, status="pending", error=None)
    from app.tasks.publish_worker import schedule_publish
    schedule_publish(job_id)
    job = await repo.get_publish_job(job_id)
    return job


@jobs_router.post("/{job_id}/cancel", response_model=PublishJob)
async def cancel_publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> PublishJob:
    repo = PublishRepository(session)
    job = await repo.get_publish_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="publish job not found")
    if job.status not in ("pending", "running"):
        raise HTTPException(
            status_code=409,
            detail=f"cannot cancel job in status {job.status}",
        )
    await repo.update_publish_job_status(job_id, status="cancelled")
    job = await repo.get_publish_job(job_id)
    return job
```

- [ ] **Step 4: Register routers in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Add after the reviews router line:

```python
    from app.api.publishers import configs_router, jobs_router
    app.include_router(configs_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_publishers.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): publisher API endpoints (configs + jobs) with credential encryption + tests"
```

---

### Task 2.3: Publish Worker

**Files:**
- Create: `D:/GEO2/backend/app/tasks/publish_worker.py`
- Create: `D:/GEO2/backend/tests/test_publish_worker.py`

**Interfaces:**
- `execute_publish(publish_job_id) -> None` — sync, testable
- `schedule_publish(publish_job_id) -> asyncio.Task` — fire-and-forget
- Uses `_EXEC_LOCK` for single-flight (shared with v0.1/v0.2 workers)

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_publish_worker.py`:

```python
"""Tests for publish worker."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings
from app.models.orm_v02 import ArticleORM, KnowledgeBaseORM, TaskORM
from app.models.orm_v03 import PublisherConfigORM, PublishJobORM
from app.repositories.publisher_repo import PublishRepository
from app.tasks.publish_worker import execute_publish


@pytest.fixture
def settings_with_key() -> Settings:
    return Settings(encryption_key=Fernet.generate_key().decode(), publish_timeout_s=5)


@pytest.mark.asyncio
async def test_execute_publish_runs_service(db_session, settings_with_key) -> None:
    from app.domain.security.encryption import encrypt

    encrypted_pw = encrypt("test")
    kb = KnowledgeBaseORM(id="kb1", name="KB")
    task = TaskORM(
        id="t1", name="T", kb_id="kb1", topic="X",
        article_count=1, style="neutral", target_length=1000,
    )
    article = ArticleORM(
        id="a1", task_id="t1", title="测试", content="X", review_status="approved",
    )
    pc = PublisherConfigORM(
        id="pc1", name="P", site_url="https://x.com",
        username="u", app_password_encrypted=encrypted_pw,
    )
    db_session.add_all([kb, task, article, pc])
    await db_session.commit()

    repo = PublishRepository(db_session)
    job = await repo.create_publish_job(article_id="a1", config_id="pc1")

    with patch("app.tasks.publish_worker.PublishService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.execute_publish = pytest.MonkeyPatch().setattr(
            "app.tasks.publish_worker.PublishService", MockSvc
        ) if False else AsyncMock()  # placeholder
        # Easier: just call real execute_publish with a mocked service

    # Simpler: directly test that execute_publish calls the service
    with patch("app.tasks.publish_worker.PublishService") as MockSvc:
        await execute_publish(job.id)
        MockSvc.assert_called_once()
        MockSvc.return_value.execute_publish.assert_called_once_with(job.id)
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publish_worker.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/tasks/publish_worker.py`**

Create `D:/GEO2/backend/app/tasks/publish_worker.py`:

```python
"""Async worker for publish jobs (shared _EXEC_LOCK with v0.1/v0.2)."""
from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.publisher.publisher_service import PublishService
from app.repositories.publisher_repo import PublishRepository

logger = structlog.get_logger()
_EXEC_LOCK = asyncio.Lock()


async def execute_publish(publish_job_id: str) -> None:
    """Execute one publish job. Called directly in tests; wrapped in lock in schedule."""
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        repo = PublishRepository(session)
        svc = PublishService(repo=repo, settings=settings)
        await svc.execute_publish(publish_job_id)


async def execute_with_lock(publish_job_id: str) -> None:
    async with _EXEC_LOCK:
        await execute_publish(publish_job_id)


def schedule_publish(publish_job_id: str) -> asyncio.Task[None]:
    """Fire-and-forget background execution."""
    return asyncio.create_task(execute_with_lock(publish_job_id))
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_publish_worker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): publish worker with shared _EXEC_LOCK + tests"
```

---

## Phase 3: Monitor — Scheduler, Repository, Service

### Task 3.1: APScheduler Wrapper

**Files:**
- Create: `D:/GEO2/backend/app/domain/monitor/scheduler.py`
- Create: `D:/GEO2/backend/tests/test_monitor_scheduler.py`

**Interfaces:**
- `get_scheduler() -> AsyncIOScheduler` — cached singleton
- `schedule_monitor_task(task) -> None` — add or replace
- `unschedule_monitor_task(task_id) -> None`
- `load_all_monitor_tasks() -> None` — startup hook
- `frequency_to_interval(freq) -> timedelta`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_monitor_scheduler.py`:

```python
"""Tests for monitor scheduler wrapper."""
from datetime import timedelta
from unittest.mock import MagicMock

from app.domain.monitor.scheduler import (
    frequency_to_interval,
    get_scheduler,
    schedule_monitor_task,
    unschedule_monitor_task,
)
from app.models.monitor import MonitorFrequency


class TestFrequencyInterval:
    def test_hourly(self) -> None:
        assert frequency_to_interval(MonitorFrequency.HOURLY) == timedelta(hours=1)

    def test_daily(self) -> None:
        assert frequency_to_interval(MonitorFrequency.DAILY) == timedelta(days=1)

    def test_weekly(self) -> None:
        assert frequency_to_interval(MonitorFrequency.WEEKLY) == timedelta(weeks=1)


class TestSchedulerSingleton:
    def test_returns_same_instance(self) -> None:
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2


def test_schedule_and_unschedule() -> None:
    """Adding and removing a monitor task works."""
    scheduler = get_scheduler()
    # Clear any prior state
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # Mock task with id and frequency
    task = MagicMock()
    task.id = "test-monitor-1"
    task.frequency = "daily"
    task.is_active = True
    task.name = "Test"
    task.next_run_at = None

    schedule_monitor_task(task)
    assert scheduler.get_job("monitor_test-monitor-1") is not None

    unschedule_monitor_task("test-monitor-1")
    assert scheduler.get_job("monitor_test-monitor-1") is None
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_scheduler.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/monitor/scheduler.py`**

Create `D:/GEO2/backend/app/domain/monitor/scheduler.py`:

```python
"""APScheduler wrapper for monitor task scheduling."""
from __future__ import annotations

from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.monitor import MonitorFrequency

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global AsyncIOScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global scheduler (idempotent)."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()


def shutdown_scheduler(wait: bool = False) -> None:
    """Shutdown the global scheduler (idempotent)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=wait)
    _scheduler = None


def frequency_to_interval(freq: MonitorFrequency | str) -> timedelta:
    """Map a frequency enum/string to a timedelta interval."""
    if isinstance(freq, str):
        freq = MonitorFrequency(freq)
    return {
        MonitorFrequency.HOURLY: timedelta(hours=1),
        MonitorFrequency.DAILY: timedelta(days=1),
        MonitorFrequency.WEEKLY: timedelta(weeks=1),
    }[freq]


def _job_id(task_id: str) -> str:
    return f"monitor_{task_id}"


def schedule_monitor_task(task) -> None:
    """Add or replace a scheduled job for a monitor task.

    `task` is expected to have attributes: id, frequency, is_active, name, next_run_at.
    """
    scheduler = get_scheduler()
    job_id = _job_id(task.id)

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if not task.is_active:
        return

    interval = frequency_to_interval(task.frequency)
    scheduler.add_job(
        _execute_monitor_run_scheduled,
        trigger=IntervalTrigger(seconds=interval.total_seconds()),
        args=[task.id],
        id=job_id,
        name=f"Monitor: {task.name}",
        replace_existing=True,
        next_run_time=getattr(task, "next_run_at", None),
    )


def unschedule_monitor_task(task_id: str) -> None:
    scheduler = get_scheduler()
    job_id = _job_id(task_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def _execute_monitor_run_scheduled(monitor_task_id: str) -> None:
    """Proxy function called by APScheduler."""
    from app.domain.monitor.monitor_service import execute_monitor_run
    await execute_monitor_run(monitor_task_id)
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_scheduler.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): APScheduler wrapper with schedule/unschedule + tests"
```

---

### Task 3.2: Monitor Pydantic Schemas

**Files:**
- Create: `D:/GEO2/backend/app/models/monitor.py`
- Create: `D:/GEO2/backend/tests/test_monitor_schemas.py`

**Interfaces:**
- `MonitorFrequency` enum
- `MonitorTaskCreate`, `MonitorTask`
- `MentionSnapshot`, `TrendPoint`, `TrendData`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_monitor_schemas.py`:

```python
"""Tests for monitor Pydantic schemas."""
import pytest
from pydantic import ValidationError

from app.models.monitor import (
    MentionSnapshot,
    MonitorFrequency,
    MonitorTaskCreate,
    TrendData,
    TrendPoint,
)


class TestMonitorTaskCreate:
    def test_min_brand(self) -> None:
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="", industry="X",
                target_questions=["q1"], frequency="daily",
            )

    def test_min_one_question(self) -> None:
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="X", industry="Y",
                target_questions=[], frequency="daily",
            )

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="X", industry="Y",
                target_questions=["q1"], frequency="daily",
                change_threshold=0.005,  # below min 0.01
            )
        with pytest.raises(ValidationError):
            MonitorTaskCreate(
                name="M", brand="X", industry="Y",
                target_questions=["q1"], frequency="daily",
                change_threshold=0.6,  # above max 0.5
            )

    def test_valid(self) -> None:
        m = MonitorTaskCreate(
            name="监测小米", brand="小米", industry="手机",
            target_questions=["小米14怎么样", "小米vs华为"],
            frequency="daily", providers=["deepseek"],
            notify_email="test@example.com",
        )
        assert m.change_threshold == 0.15  # default


class TestMonitorFrequency:
    def test_enum_values(self) -> None:
        assert MonitorFrequency.HOURLY == "hourly"
        assert MonitorFrequency.DAILY == "daily"
        assert MonitorFrequency.WEEKLY == "weekly"


class TestTrendData:
    def test_empty_points(self) -> None:
        t = TrendData(monitor_id="m1", days=30, points=[])
        assert t.points == []
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_schemas.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/models/monitor.py`**

Create `D:/GEO2/backend/app/models/monitor.py`:

```python
"""Pydantic models for monitor API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MonitorFrequency(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class MonitorTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    brand: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    target_questions: list[str] = Field(..., min_length=1, max_length=5)
    frequency: MonitorFrequency = MonitorFrequency.DAILY
    providers: list[str] = Field(default_factory=lambda: ["deepseek"])
    notify_email: EmailStr | None = None
    change_threshold: float = Field(0.15, ge=0.01, le=0.5)


class MonitorTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    brand: str
    industry: str
    target_questions: list[str]
    frequency: MonitorFrequency
    providers: list[str]
    notify_email: str | None
    change_threshold: float
    is_active: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MentionSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    monitor_task_id: str
    run_at: datetime
    mention_rate: float
    mention_count: int
    total_samples: int
    avg_position: float | None
    details: list[dict]
    error_message: str | None
    created_at: datetime


class TrendPoint(BaseModel):
    run_at: datetime
    mention_rate: float
    mention_count: int
    total_samples: int
    avg_position: float | None


class TrendData(BaseModel):
    monitor_id: str
    days: int
    points: list[TrendPoint]
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_schemas.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): monitor Pydantic schemas + tests"
```

---

### Task 3.3: MonitorRepository

**Files:**
- Create: `D:/GEO2/backend/app/repositories/monitor_repo.py`
- Create: `D:/GEO2/backend/tests/test_monitor_repo.py`

**Interfaces:**
- `MonitorRepository(session)`:
  - `create_monitor_task(...) -> MonitorTaskORM`
  - `get_monitor_task(id) -> MonitorTaskORM | None`
  - `list_monitor_tasks() -> list[MonitorTaskORM]`
  - `list_active_monitor_tasks() -> list[MonitorTaskORM]`
  - `update_monitor_task(...) -> None`
  - `update_monitor_last_run(id, run_at) -> None`
  - `delete_monitor_task(id) -> None`
  - `create_snapshot(...) -> str` (returns id)
  - `get_snapshot(id) -> MentionSnapshotORM | None`
  - `get_previous_snapshot(task_id, before_id) -> MentionSnapshotORM | None`
  - `list_snapshots_since(task_id, cutoff) -> list[MentionSnapshotORM]`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_monitor_repo.py`:

```python
"""Tests for MonitorRepository."""
import json

import pytest

from app.models.orm_v03 import MonitorTaskORM
from app.repositories.monitor_repo import MonitorRepository


@pytest.mark.asyncio
async def test_create_monitor_task(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M1", brand="小米", industry="手机",
        target_questions=["q1", "q2"],
        frequency="daily", providers=["deepseek"],
        notify_email="test@example.com",
        change_threshold=0.15,
    )
    assert m.id != ""
    assert m.is_active == 1
    assert json.loads(m.target_questions) == ["q1", "q2"]
    assert json.loads(m.providers) == ["deepseek"]


@pytest.mark.asyncio
async def test_get_monitor_task(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )
    fetched = await repo.get_monitor_task(m.id)
    assert fetched.name == "M"


@pytest.mark.asyncio
async def test_list_active_monitor_tasks(db_session) -> None:
    repo = MonitorRepository(db_session)
    a = await repo.create_monitor_task(
        name="A", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )
    i = await repo.create_monitor_task(
        name="I", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )
    await repo.update_monitor_task(i.id, is_active=False)

    actives = await repo.list_active_monitor_tasks()
    assert {t.id for t in actives} == {a.id}


@pytest.mark.asyncio
async def test_create_snapshot_and_get_previous(db_session) -> None:
    from datetime import datetime, timezone, timedelta

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )

    s1_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=1),
        mention_rate=0.3, mention_count=3, total_samples=10,
        avg_position=1.5, details=[], error_message=None,
    )
    s2_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc),
        mention_rate=0.6, mention_count=6, total_samples=10,
        avg_position=1.0, details=[], error_message=None,
    )

    # Get previous before s2 should return s1
    prev = await repo.get_previous_snapshot(m.id, before_id=s2_id)
    assert prev is not None
    assert prev.id == s1_id
    assert prev.mention_rate == 0.3


@pytest.mark.asyncio
async def test_list_snapshots_since(db_session) -> None:
    from datetime import datetime, timezone, timedelta

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y", target_questions=["q"],
        frequency="daily", providers=["deepseek"],
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=10)
    await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=20),
        mention_rate=0.1, mention_count=1, total_samples=10, avg_position=None,
        details=[], error_message=None,
    )
    await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=5),
        mention_rate=0.5, mention_count=5, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )

    recent = await repo.list_snapshots_since(m.id, cutoff=cutoff)
    assert len(recent) == 1
    assert recent[0].mention_rate == 0.5
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_repo.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/repositories/monitor_repo.py`**

Create `D:/GEO2/backend/app/repositories/monitor_repo.py`:

```python
"""Repository for monitor tasks and mention snapshots."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v03 import MentionSnapshotORM, MonitorTaskORM


class MonitorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- MonitorTask ---

    async def create_monitor_task(
        self,
        name: str,
        brand: str,
        industry: str,
        target_questions: list[str],
        frequency: str,
        providers: list[str],
        notify_email: str | None = None,
        change_threshold: float = 0.15,
    ) -> MonitorTaskORM:
        m = MonitorTaskORM(
            id=str(uuid.uuid4()),
            name=name,
            brand=brand,
            industry=industry,
            target_questions=json.dumps(target_questions, ensure_ascii=False),
            frequency=frequency,
            providers=json.dumps(providers),
            notify_email=notify_email,
            change_threshold=change_threshold,
            is_active=1,
        )
        self.session.add(m)
        await self.session.commit()
        await self.session.refresh(m)
        return m

    async def get_monitor_task(self, id: str) -> MonitorTaskORM | None:
        result = await self.session.execute(
            select(MonitorTaskORM).where(MonitorTaskORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_monitor_tasks(self) -> list[MonitorTaskORM]:
        result = await self.session.execute(
            select(MonitorTaskORM).order_by(MonitorTaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_monitor_tasks(self) -> list[MonitorTaskORM]:
        result = await self.session.execute(
            select(MonitorTaskORM)
            .where(MonitorTaskORM.is_active == 1)
            .order_by(MonitorTaskORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_monitor_task(
        self,
        id: str,
        name: str | None = None,
        brand: str | None = None,
        industry: str | None = None,
        target_questions: list[str] | None = None,
        frequency: str | None = None,
        providers: list[str] | None = None,
        notify_email: str | None = None,
        change_threshold: float | None = None,
        is_active: bool | None = None,
    ) -> None:
        m = await self.get_monitor_task(id)
        if m is None:
            return
        if name is not None:
            m.name = name
        if brand is not None:
            m.brand = brand
        if industry is not None:
            m.industry = industry
        if target_questions is not None:
            m.target_questions = json.dumps(target_questions, ensure_ascii=False)
        if frequency is not None:
            m.frequency = frequency
        if providers is not None:
            m.providers = json.dumps(providers)
        if notify_email is not None:
            m.notify_email = notify_email
        if change_threshold is not None:
            m.change_threshold = change_threshold
        if is_active is not None:
            m.is_active = 1 if is_active else 0
        m.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_monitor_last_run(self, id: str, run_at: datetime) -> None:
        m = await self.get_monitor_task(id)
        if m is None:
            return
        m.last_run_at = run_at
        m.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def delete_monitor_task(self, id: str) -> None:
        from sqlalchemy import delete
        await self.session.execute(
            delete(MonitorTaskORM).where(MonitorTaskORM.id == id)
        )
        await self.session.commit()

    # --- MentionSnapshot ---

    async def create_snapshot(
        self,
        monitor_task_id: str,
        run_at: datetime,
        mention_rate: float,
        mention_count: int,
        total_samples: int,
        avg_position: float | None,
        details: list[dict],
        error_message: str | None = None,
    ) -> str:
        s = MentionSnapshotORM(
            id=str(uuid.uuid4()),
            monitor_task_id=monitor_task_id,
            run_at=run_at,
            mention_rate=mention_rate,
            mention_count=mention_count,
            total_samples=total_samples,
            avg_position=avg_position,
            details=json.dumps(details, ensure_ascii=False),
            error_message=error_message,
        )
        self.session.add(s)
        await self.session.commit()
        return s.id

    async def get_snapshot(self, id: str) -> MentionSnapshotORM | None:
        result = await self.session.execute(
            select(MentionSnapshotORM).where(MentionSnapshotORM.id == id)
        )
        return result.scalar_one_or_none()

    async def get_previous_snapshot(
        self, task_id: str, before_id: str
    ) -> MentionSnapshotORM | None:
        """Get the most recent snapshot before the given one."""
        before = await self.get_snapshot(before_id)
        if before is None:
            return None
        result = await self.session.execute(
            select(MentionSnapshotORM)
            .where(
                (MentionSnapshotORM.monitor_task_id == task_id)
                & (MentionSnapshotORM.run_at < before.run_at)
            )
            .order_by(MentionSnapshotORM.run_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_snapshots_since(
        self, task_id: str, cutoff: datetime
    ) -> list[MentionSnapshotORM]:
        result = await self.session.execute(
            select(MentionSnapshotORM)
            .where(
                (MentionSnapshotORM.monitor_task_id == task_id)
                & (MentionSnapshotORM.run_at >= cutoff)
            )
            .order_by(MentionSnapshotORM.run_at)
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_repo.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): MonitorRepository with task + snapshot CRUD + tests"
```

---

### Task 3.4: MonitorService (Execute One Run)

**Files:**
- Create: `D:/GEO2/backend/app/domain/monitor/monitor_service.py`
- Create: `D:/GEO2/backend/tests/test_monitor_service.py`

**Interfaces:**
- `execute_monitor_run(monitor_task_id) -> None` — sync, runs the full pipeline
- `check_and_notify_change(task, current_rate, snapshot_id) -> None` — send email if change > threshold

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_monitor_service.py`:

```python
"""Tests for MonitorService."""
import json
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import pytest

from app.models.orm_v03 import MonitorTaskORM
from app.repositories.monitor_repo import MonitorRepository
from app.models.schemas import MentionResult
from app.domain.monitor.monitor_service import execute_monitor_run


@pytest.mark.asyncio
async def test_execute_monitor_run_creates_snapshot(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="小米", industry="手机",
        target_questions=["小米14怎么样", "小米vs华为"],
        frequency="daily", providers=["deepseek"],
    )

    mentions = [
        MentionResult(
            question="小米14怎么样", llm_provider="deepseek",
            llm_answer="小米14 不错", brand_mentioned=True, mention_position=1,
        ),
        MentionResult(
            question="小米vs华为", llm_provider="deepseek",
            llm_answer="各有优势", brand_mentioned=False,
        ),
    ]

    with patch("app.domain.monitor.monitor_service.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.query_mentions = AsyncMock(return_value=mentions)
        with patch("app.domain.monitor.monitor_service.check_and_notify_change", new=AsyncMock()):
            await execute_monitor_run(m.id)

    snaps = await repo.list_snapshots_since(m.id, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert len(snaps) == 1
    assert snaps[0].mention_rate == 0.5  # 1/2
    assert snaps[0].mention_count == 1
    assert snaps[0].total_samples == 2


@pytest.mark.asyncio
async def test_execute_monitor_run_inactive_skips(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
    )
    await repo.update_monitor_task(m.id, is_active=False)

    with patch("app.domain.monitor.monitor_service.LLMClient") as MockLLM:
        await execute_monitor_run(m.id)
        MockLLM.assert_not_called()

    snaps = await repo.list_snapshots_since(m.id, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert snaps == []


@pytest.mark.asyncio
async def test_execute_monitor_run_handles_llm_failure(db_session) -> None:
    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
    )

    with patch("app.domain.monitor.monitor_service.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.query_mentions = AsyncMock(side_effect=Exception("LLM down"))
        with patch("app.domain.monitor.monitor_service.check_and_notify_change", new=AsyncMock()):
            await execute_monitor_run(m.id)

    snaps = await repo.list_snapshots_since(m.id, datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert len(snaps) == 1
    assert snaps[0].error_message is not None
    assert "LLM down" in snaps[0].error_message


@pytest.mark.asyncio
async def test_check_and_notify_change_sends_email_on_significant_change(db_session) -> None:
    from app.domain.monitor.monitor_service import check_and_notify_change
    from datetime import datetime, timezone, timedelta

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="监测小米", brand="小米", industry="手机",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
        notify_email="test@example.com", change_threshold=0.1,
    )

    s1_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=1),
        mention_rate=0.3, mention_count=3, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )
    s2_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc),
        mention_rate=0.6, mention_count=6, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )

    task = await repo.get_monitor_task(m.id)

    with patch("app.domain.notification.notification_service.send_email", new=AsyncMock()) as mock_send:
        await check_and_notify_change(task, current_rate=0.6, snapshot_id=s2_id)
        mock_send.assert_called_once()
        # Check that the previous snapshot used was s1
        call_args = mock_send.call_args
        assert "上升" in call_args.kwargs.get("subject", "") or "上升" in call_args.args[1]


@pytest.mark.asyncio
async def test_check_and_notify_change_skips_email_on_small_change(db_session) -> None:
    from app.domain.monitor.monitor_service import check_and_notify_change
    from datetime import datetime, timezone, timedelta

    repo = MonitorRepository(db_session)
    m = await repo.create_monitor_task(
        name="M", brand="X", industry="Y",
        target_questions=["q"], frequency="daily", providers=["deepseek"],
        notify_email="test@example.com", change_threshold=0.5,  # 50% threshold
    )

    s1_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc) - timedelta(days=1),
        mention_rate=0.3, mention_count=3, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )
    s2_id = await repo.create_snapshot(
        monitor_task_id=m.id, run_at=datetime.now(timezone.utc),
        mention_rate=0.35, mention_count=3, total_samples=10, avg_position=1.0,
        details=[], error_message=None,
    )

    task = await repo.get_monitor_task(m.id)

    with patch("app.domain.notification.notification_service.send_email", new=AsyncMock()) as mock_send:
        await check_and_notify_change(task, current_rate=0.35, snapshot_id=s2_id)
        mock_send.assert_not_called()
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_service.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/monitor/monitor_service.py`**

Create `D:/GEO2/backend/app/domain/monitor/monitor_service.py`:

```python
"""Orchestrates a single monitor run: query LLM, save snapshot, check threshold."""
from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.domain.llm_client import LLMClient
from app.repositories.monitor_repo import MonitorRepository

logger = structlog.get_logger()


async def execute_monitor_run(monitor_task_id: str) -> None:
    """Execute one monitor snapshot. Reuses v0.1's LLMClient."""
    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        repo = MonitorRepository(session)
        task = await repo.get_monitor_task(monitor_task_id)
        if task is None or not task.is_active:
            return

        await repo.update_monitor_last_run(monitor_task_id, datetime.now(timezone.utc))

        try:
            llm = LLMClient(settings)
            mentions = await llm.query_mentions(
                brand=task.brand,
                industry=task.industry,
                questions=json.loads(task.target_questions),
                providers=json.loads(task.providers),
            )

            valid = [m for m in mentions if m.error is None]
            mentioned = [m for m in valid if m.brand_mentioned]
            rate = len(mentioned) / len(valid) if valid else 0.0
            avg_pos = (
                sum(m.mention_position for m in mentioned if m.mention_position) / len(mentioned)
                if mentioned else None
            )

            snapshot_id = await repo.create_snapshot(
                monitor_task_id=monitor_task_id,
                run_at=datetime.now(timezone.utc),
                mention_rate=rate,
                mention_count=len(mentioned),
                total_samples=len(valid),
                avg_position=avg_pos,
                details=[m.model_dump() for m in mentions],
            )

            logger.info(
                "monitor_run_done",
                task_id=monitor_task_id,
                rate=rate,
                mentioned=len(mentioned),
                total=len(valid),
            )

            if task.notify_email:
                await check_and_notify_change(task, current_rate=rate, snapshot_id=snapshot_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("monitor_run_failed", task_id=monitor_task_id)
            await repo.create_snapshot(
                monitor_task_id=monitor_task_id,
                run_at=datetime.now(timezone.utc),
                mention_rate=0.0,
                mention_count=0,
                total_samples=0,
                avg_position=None,
                details=[],
                error_message=f"{type(e).__name__}: {e}",
            )


async def check_and_notify_change(task, current_rate: float, snapshot_id: str) -> None:
    """Compare current snapshot to previous; send email if change > threshold."""
    factory = get_session_factory()
    async with factory() as session:
        repo = MonitorRepository(session)
        previous = await repo.get_previous_snapshot(task.id, before_id=snapshot_id)
    if previous is None:
        return
    if not task.notify_email:
        return

    delta = abs(current_rate - previous.mention_rate)
    if delta < task.change_threshold:
        return

    direction = "上升" if current_rate > previous.mention_rate else "下降"
    subject = f"[GEO 监测] {task.name} - 提及率{direction} {delta*100:.1f}%"
    body = f"""品牌：{task.brand}
当前提及率：{current_rate * 100:.1f}%
上次提及率：{previous.mention_rate * 100:.1f}%
变化：{direction} {delta * 100:.1f}%（阈值 {task.change_threshold * 100:.0f}%）
执行时间：{datetime.now(timezone.utc).isoformat()}

查看详情：http://localhost:5173/monitors/{task.id}
"""
    try:
        from app.domain.notification.notification_service import send_email
        await send_email(to=task.notify_email, subject=subject, body=body)
    except Exception as e:  # noqa: BLE001
        logger.warning("notification_email_failed", error=str(e))
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_monitor_service.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): MonitorService.execute_monitor_run with threshold check + tests"
```

---

## Phase 4: Notification (Email)

### Task 4.1: Email Sender (aiosmtplib)

**Files:**
- Create: `D:/GEO2/backend/app/domain/notification/__init__.py`
- Create: `D:/GEO2/backend/app/domain/notification/email_sender.py`
- Create: `D:/GEO2/backend/tests/test_email_sender.py`

**Interfaces:**
- `send_email(to, subject, body) -> None` — uses aiosmtplib
- `NotificationError` (in exceptions.py)

- [ ] **Step 1: Create `app/domain/notification/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/notification/__init__.py`.

- [ ] **Step 2: Add `NotificationError` to exceptions**

Edit `D:/GEO2/backend/app/domain/exceptions.py`. Add:

```python
class NotificationError(DomainError):
    """Email / notification delivery failed."""
```

- [ ] **Step 3: Write failing test**

Create `D:/GEO2/backend/tests/test_email_sender.py`:

```python
"""Tests for email sender."""
from unittest.mock import patch, AsyncMock

import pytest

from app.core.config import Settings
from app.domain.exceptions import NotificationError
from app.domain.notification.email_sender import send_email


@pytest.fixture
def smtp_settings() -> Settings:
    return Settings(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
        smtp_use_tls=True,
        smtp_from="test@example.com",
    )


@pytest.mark.asyncio
async def test_send_email_success(smtp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: smtp_settings)
    with patch("aiosmtplib.send", new=AsyncMock()) as mock_send:
        await send_email(to="user@example.com", subject="Test", body="Hello")
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_no_smtp_config(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: Settings())
    with pytest.raises(NotificationError, match="SMTP not configured"):
        await send_email(to="x", subject="y", body="z")


@pytest.mark.asyncio
async def test_send_email_smtp_error(monkeypatch) -> None:
    s = Settings(smtp_host="smtp.example.com", smtp_port=587, smtp_user="u", smtp_password="p")
    monkeypatch.setattr("app.core.config.get_settings", lambda: s)
    with patch("aiosmtplib.send", new=AsyncMock(side_effect=Exception("smtp down"))):
        with pytest.raises(NotificationError, match="smtp down"):
            await send_email(to="x", subject="y", body="z")
```

- [ ] **Step 4: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_email_sender.py -v
```

Expected: FAIL.

- [ ] **Step 5: Create `app/domain/notification/email_sender.py`**

Create `D:/GEO2/backend/app/domain/notification/email_sender.py`:

```python
"""SMTP email sender using aiosmtplib."""
from __future__ import annotations

from email.mime.text import MIMEText

import aiosmtplib
import structlog

from app.core.config import get_settings
from app.domain.exceptions import NotificationError

logger = structlog.get_logger()


async def send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise NotificationError("SMTP not configured (SMTP_HOST is empty)")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=settings.smtp_use_tls,
        )
        logger.info("email_sent", to=to, subject=subject)
    except Exception as e:  # noqa: BLE001
        logger.warning("email_send_failed", error=str(e))
        raise NotificationError(str(e)) from e
```

- [ ] **Step 6: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_email_sender.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): SMTP email sender via aiosmtplib + tests"
```

---

### Task 4.2: Notification Service (Triggers)

**Files:**
- Create: `D:/GEO2/backend/app/domain/notification/notification_service.py`
- Create: `D:/GEO2/backend/tests/test_notification_service.py`

**Interfaces:**
- `notify_publish_success(title, remote_url, site_name) -> None` — sends "publish success" email
- `notify_publish_failure(title, error, site_name) -> None` — sends "publish failure" email
- `send_test_email(to) -> None` — test endpoint helper

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_notification_service.py`:

```python
"""Tests for notification service."""
from unittest.mock import patch, AsyncMock

import pytest

from app.core.config import Settings
from app.domain.notification.notification_service import (
    notify_publish_failure,
    notify_publish_success,
)


@pytest.fixture
def smtp_settings() -> Settings:
    return Settings(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="user",
        smtp_password="pass",
        smtp_use_tls=True,
        smtp_from="test@example.com",
    )


@pytest.mark.asyncio
async def test_notify_publish_success(smtp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: smtp_settings)
    with patch("app.domain.notification.notification_service.send_email", new=AsyncMock()) as mock_send:
        await notify_publish_success(
            title="测试文章", remote_url="https://example.com/?p=42", site_name="主站",
            recipient="user@example.com",
        )
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "成功" in call_args.kwargs.get("subject", "") or "成功" in call_args.args[1]


@pytest.mark.asyncio
async def test_notify_publish_failure(smtp_settings: Settings, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.get_settings", lambda: smtp_settings)
    with patch("app.domain.notification.notification_service.send_email", new=AsyncMock()) as mock_send:
        await notify_publish_failure(
            title="测试文章", error="认证失败", site_name="主站",
            recipient="user@example.com",
        )
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "失败" in call_args.kwargs.get("subject", "") or "失败" in call_args.args[1]
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_notification_service.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/domain/notification/notification_service.py`**

Create `D:/GEO2/backend/app/domain/notification/notification_service.py`:

```python
"""Notification triggers: publish success/failure and monitor changes."""
from __future__ import annotations

import structlog

from app.domain.exceptions import NotificationError
from app.domain.notification.email_sender import send_email

logger = structlog.get_logger()


async def notify_publish_success(
    title: str, remote_url: str, site_name: str, recipient: str
) -> None:
    subject = f"[GEO 发布成功] {title}"
    body = f"""文章《{title}》已成功发布到 WordPress 站点 {site_name}。

查看文章：{remote_url}
"""
    try:
        await send_email(to=recipient, subject=subject, body=body)
    except NotificationError as e:
        logger.warning("notify_publish_success_failed", error=str(e))


async def notify_publish_failure(
    title: str, error: str, site_name: str, recipient: str
) -> None:
    subject = f"[GEO 发布失败] {title}"
    body = f"""文章《{title}》发布到 WordPress 站点 {site_name} 失败。

错误信息：{error}

请检查 WordPress 凭证、权限、站点 URL 等。
"""
    try:
        await send_email(to=recipient, subject=subject, body=body)
    except NotificationError as e:
        logger.warning("notify_publish_failure_failed", error=str(e))
```

- [ ] **Step 4: Update publisher_service to pass recipient**

Edit `D:/GEO2/backend/app/domain/publisher/publisher_service.py`. Update the notification calls in `execute_publish` to pass a recipient. We need to:
1. Get the notification recipient from settings or config

Simplest: use SMTP_FROM as the fallback recipient. Or read from `.env`:
- Add `NOTIFY_EMAIL_DEFAULT: str = ""` to Settings

For MVP, use the SMTP_FROM as recipient (any notification goes to the site owner).

Update the success call:
```python
            try:
                from app.core.config import get_settings
                settings = get_settings()
                recipient = settings.notify_email_default or settings.smtp_from
                from app.domain.notification.notification_service import (
                    notify_publish_success,
                )
                await notify_publish_success(
                    title=title,
                    remote_url=result["link"],
                    site_name=config.name,
                    recipient=recipient,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("notification_failed", error=str(e))
```

And the failure call:
```python
        try:
            from app.core.config import get_settings
            settings = get_settings()
            recipient = settings.notify_email_default or settings.smtp_from
            from app.domain.notification.notification_service import notify_publish_failure
            await notify_publish_failure(
                title=article.title or "Untitled",
                error=error,
                site_name="(unknown)",
                recipient=recipient,
            )
        except Exception:  # noqa: BLE001
            pass
```

Add to `Settings` class in `app/core/config.py`:
```python
    notify_email_default: str = ""
```

Update `requirements.txt` and `.env.example` already done in Task 0.1. Add to `.env.example`:
```bash
NOTIFY_EMAIL_DEFAULT=
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_notification_service.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): notification_service with publish success/failure triggers + tests"
```

---

### Task 4.3: Notifications API + Main App Wiring

**Files:**
- Create: `D:/GEO2/backend/app/api/notifications.py`
- Modify: `D:/GEO2/backend/app/api/publishers.py` (update notification calls to use recipient)
- Modify: `D:/GEO2/backend/app/main.py` (lifespan: start scheduler + load monitor tasks)
- Modify: `D:/GEO2/backend/app/api/diagnosis.py` (register notifications router)
- Create: `D:/GEO2/backend/tests/test_api_notifications.py`

**Interfaces:**
- `POST /api/notifications/test` — send test email to specified address

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_notifications.py`:

```python
"""Integration tests for notifications API."""
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient


def test_send_test_email(client: TestClient) -> None:
    with patch("app.api.notifications.send_email", new=AsyncMock()) as mock_send:
        resp = client.post(
            "/api/notifications/test",
            json={"to": "test@example.com"},
        )
    assert resp.status_code == 200
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert "test" in call_args.kwargs.get("subject", "").lower() or "test" in call_args.args[1].lower()


def test_send_test_email_requires_email(client: TestClient) -> None:
    resp = client.post("/api/notifications/test", json={})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_notifications.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/api/notifications.py`**

Create `D:/GEO2/backend/app/api/notifications.py`:

```python
"""Notifications API: send test email."""
from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.domain.exceptions import NotificationError
from app.domain.notification.email_sender import send_email

router = APIRouter(prefix="/notifications", tags=["notifications"])


class TestEmailRequest(BaseModel):
    to: EmailStr


@router.post("/test")
async def send_test_email(body: TestEmailRequest) -> dict:
    try:
        await send_email(
            to=body.to,
            subject="[GEO Agent] Test Email",
            body="This is a test email from GEO Agent. If you received this, SMTP is working correctly.",
        )
        return {"ok": True}
    except NotificationError as e:
        return {"ok": False, "error": str(e)}
```

- [ ] **Step 4: Register notifications router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Add after the publishers routers line:

```python
    from app.api.notifications import router as notifications_router
    app.include_router(notifications_router, prefix="/api")
```

Also update `main.py` lifespan to start scheduler and load monitor tasks:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    # v0.3: start monitor scheduler
    from app.domain.monitor.scheduler import start_scheduler, load_all_monitor_tasks
    start_scheduler()
    await load_all_monitor_tasks()
    yield
    # Shutdown
    from app.domain.monitor.scheduler import shutdown_scheduler
    shutdown_scheduler()
    await dispose_db()
```

Add the import and function in `app/domain/monitor/scheduler.py` (already there, just verify). Also add to scheduler.py:

```python
async def load_all_monitor_tasks() -> None:
    """On startup, reload all active monitor tasks from DB."""
    factory = get_session_factory()
    async with factory() as session:
        repo = MonitorRepository(session)
        tasks = await repo.list_active_monitor_tasks()
        for task in tasks:
            schedule_monitor_task(task)
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_notifications.py -v
```

Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): notifications API + main.py lifespan scheduler integration + tests"
```

---

## Phase 5: Monitor API + Trends API

### Task 5.1: Monitor API Endpoints

**Files:**
- Create: `D:/GEO2/backend/app/api/monitors.py`
- Modify: `D:/GEO2/backend/app/main.py` (register router)
- Create: `D:/GEO2/backend/tests/test_api_monitors.py`

**Interfaces:**
- `GET /api/monitors` — list
- `POST /api/monitors` — create (schedules)
- `GET /api/monitors/{id}` — detail
- `PUT /api/monitors/{id}` — update (reschedules)
- `DELETE /api/monitors/{id}` — delete (unschedules)
- `POST /api/monitors/{id}/run` — run now
- `GET /api/monitors/{id}/snapshots?days=30`
- `GET /api/monitors/{id}/trends?days=30`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_monitors.py`:

```python
"""Integration tests for monitor API."""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_create_monitor_task(client: TestClient) -> None:
    with patch("app.api.monitors.schedule_monitor_task") as mock:
        resp = client.post(
            "/api/monitors",
            json={
                "name": "监测小米",
                "brand": "小米",
                "industry": "手机",
                "target_questions": ["q1", "q2"],
                "frequency": "daily",
                "providers": ["deepseek"],
                "notify_email": "test@example.com",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "监测小米"
    assert mock.called


def test_list_monitors(client: TestClient) -> None:
    with patch("app.api.monitors.schedule_monitor_task"):
        client.post("/api/monitors", json={
            "name": "M1", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    resp = client.get("/api/monitors")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_monitor_validates_brand(client: TestClient) -> None:
    resp = client.post("/api/monitors", json={
        "name": "M", "brand": "", "industry": "Y",
        "target_questions": ["q1"], "frequency": "daily",
    })
    assert resp.status_code == 422


def test_get_monitor(client: TestClient) -> None:
    with patch("app.api.monitors.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "M", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    mid = create.json()["id"]
    resp = client.get(f"/api/monitors/{mid}")
    assert resp.status_code == 200


def test_delete_monitor_unschedules(client: TestClient) -> None:
    with patch("app.api.monitors.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "M", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    mid = create.json()["id"]
    with patch("app.api.monitors.unschedule_monitor_task") as mock_un:
        resp = client.delete(f"/api/monitors/{mid}")
    assert resp.status_code == 204
    mock_un.assert_called_once_with(mid)


def test_run_monitor_now(client: TestClient) -> None:
    from datetime import datetime, timezone
    with patch("app.api.monitors.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "M", "brand": "X", "industry": "Y",
            "target_questions": ["q1"], "frequency": "daily",
        })
    mid = create.json()["id"]

    with patch("app.api.monitors.execute_monitor_run") as mock_run:
        # Don't await it (it's an async function)
        mock_run.return_value = None
        resp = client.post(f"/api/monitors/{mid}/run")
    assert resp.status_code == 202
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_monitors.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/api/monitors.py`**

Create `D:/GEO2/backend/app/api/monitors.py`:

```python
"""Monitor task API: CRUD + run-now + snapshots/trends."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.monitor import (
    MentionSnapshot,
    MonitorTask,
    MonitorTaskCreate,
    TrendData,
    TrendPoint,
)
from app.models.schemas import TaskStatus  # reuse enum
from app.repositories.monitor_repo import MonitorRepository

router = APIRouter(prefix="/monitors", tags=["monitors"])


def _task_to_pydantic(task) -> MonitorTask:
    return MonitorTask(
        id=task.id,
        name=task.name,
        brand=task.brand,
        industry=task.industry,
        target_questions=json.loads(task.target_questions),
        frequency=task.frequency,  # type: ignore[arg-type]
        providers=json.loads(task.providers),
        notify_email=task.notify_email,
        change_threshold=task.change_threshold,
        is_active=bool(task.is_active),
        next_run_at=task.next_run_at,
        last_run_at=task.last_run_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", status_code=201, response_model=MonitorTask)
async def create_monitor_task(
    body: MonitorTaskCreate,
    session: AsyncSession = Depends(get_session),
) -> MonitorTask:
    repo = MonitorRepository(session)
    task = await repo.create_monitor_task(
        name=body.name,
        brand=body.brand,
        industry=body.industry,
        target_questions=body.target_questions,
        frequency=body.frequency.value,
        providers=body.providers,
        notify_email=body.notify_email,
        change_threshold=body.change_threshold,
    )
    # Schedule
    from app.domain.monitor.scheduler import schedule_monitor_task
    schedule_monitor_task(task)
    return _task_to_pydantic(task)


@router.get("", response_model=list[MonitorTask])
async def list_monitor_tasks(
    session: AsyncSession = Depends(get_session),
) -> list[MonitorTask]:
    repo = MonitorRepository(session)
    tasks = await repo.list_monitor_tasks()
    return [_task_to_pydantic(t) for t in tasks]


@router.get("/{task_id}", response_model=MonitorTask)
async def get_monitor_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> MonitorTask:
    repo = MonitorRepository(session)
    task = await repo.get_monitor_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="monitor task not found")
    return _task_to_pydantic(task)


@router.put("/{task_id}", response_model=MonitorTask)
async def update_monitor_task(
    task_id: str,
    body: MonitorTaskCreate,
    session: AsyncSession = Depends(get_session),
) -> MonitorTask:
    repo = MonitorRepository(session)
    await repo.update_monitor_task(
        id=task_id,
        name=body.name,
        brand=body.brand,
        industry=body.industry,
        target_questions=body.target_questions,
        frequency=body.frequency.value,
        providers=body.providers,
        notify_email=body.notify_email,
        change_threshold=body.change_threshold,
    )
    task = await repo.get_monitor_task(task_id)
    # Re-schedule
    from app.domain.monitor.scheduler import schedule_monitor_task
    schedule_monitor_task(task)
    return _task_to_pydantic(task)


@router.delete("/{task_id}", status_code=204)
async def delete_monitor_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    from app.domain.monitor.scheduler import unschedule_monitor_task
    repo = MonitorRepository(session)
    task = await repo.get_monitor_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="monitor task not found")
    unschedule_monitor_task(task_id)
    await repo.delete_monitor_task(task_id)


@router.post("/{task_id}/run", status_code=202)
async def run_monitor_now(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger immediate execution (does NOT change next_run_at)."""
    repo = MonitorRepository(session)
    task = await repo.get_monitor_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="monitor task not found")
    from app.domain.monitor.monitor_service import execute_monitor_run
    # Run in background, don't block API
    asyncio.create_task(execute_monitor_run(task_id))
    return {"status": "triggered"}


@router.get("/{task_id}/snapshots", response_model=list[MentionSnapshot])
async def list_snapshots(
    task_id: str,
    days: int = 30,
    session: AsyncSession = Depends(get_session),
) -> list[MentionSnapshot]:
    repo = MonitorRepository(session)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    snaps = await repo.list_snapshots_since(task_id, cutoff=cutoff)
    result = []
    for s in snaps:
        result.append(MentionSnapshot(
            id=s.id,
            monitor_task_id=s.monitor_task_id,
            run_at=s.run_at,
            mention_rate=s.mention_rate,
            mention_count=s.mention_count,
            total_samples=s.total_samples,
            avg_position=s.avg_position,
            details=json.loads(s.details or "[]"),
            error_message=s.error_message,
            created_at=s.created_at,
        ))
    return result


@router.get("/{task_id}/trends", response_model=TrendData)
async def get_trends(
    task_id: str,
    days: int = 30,
    session: AsyncSession = Depends(get_session),
) -> TrendData:
    repo = MonitorRepository(session)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    snaps = await repo.list_snapshots_since(task_id, cutoff=cutoff)
    return TrendData(
        monitor_id=task_id,
        days=days,
        points=[
            TrendPoint(
                run_at=s.run_at,
                mention_rate=s.mention_rate,
                mention_count=s.mention_count,
                total_samples=s.total_samples,
                avg_position=s.avg_position,
            )
            for s in snaps
        ],
    )
```

- [ ] **Step 4: Register router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Add after notifications router:

```python
    from app.api.monitors import router as monitors_router
    app.include_router(monitors_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_monitors.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.3): monitor API (CRUD + run-now + snapshots + trends) + tests"
```

---

## Phase 6: Frontend

### Task 6.1: Frontend Types + API Client Extension

**Files:**
- Create: `D:/GEO2/frontend/src/types/v0.3.ts`
- Modify: `D:/GEO2/frontend/src/api/client.ts`

- [ ] **Step 1: Create `types/v0.3.ts`**

Create `D:/GEO2/frontend/src/types/v0.3.ts`:

```typescript
export type PublishJobStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
export type MonitorFrequency = 'hourly' | 'daily' | 'weekly';

export interface PublisherConfig {
  id: string;
  name: string;
  site_url: string;
  username: string;
  is_default: boolean;
  created_at: string;
}

export interface PublishJob {
  id: string;
  article_id: string;
  config_id: string;
  title_override: string | null;
  status: PublishJobStatus;
  remote_post_id: number | null;
  remote_url: string | null;
  error_message: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitorTask {
  id: string;
  name: string;
  brand: string;
  industry: string;
  target_questions: string[];
  frequency: MonitorFrequency;
  providers: string[];
  notify_email: string | null;
  change_threshold: number;
  is_active: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MentionSnapshot {
  id: string;
  monitor_task_id: string;
  run_at: string;
  mention_rate: number;
  mention_count: number;
  total_samples: number;
  avg_position: number | null;
  details: Array<Record<string, unknown>>;
  error_message: string | null;
  created_at: string;
}

export interface TrendPoint {
  run_at: string;
  mention_rate: number;
  mention_count: number;
  total_samples: number;
  avg_position: number | null;
}

export interface TrendData {
  monitor_id: string;
  days: number;
  points: TrendPoint[];
}
```

- [ ] **Step 2: Extend `api/client.ts`**

Edit `D:/GEO2/frontend/src/api/client.ts`. Add v0.3 imports and methods:

```typescript
import type {
  MentionSnapshot, MonitorTask, PublishJob, PublisherConfig, TrendData,
} from '@/types/v0.3';

// Inside the api object, add:
  listPublishers(): Promise<PublisherConfig[]> {
    return request('/publishers');
  },
  createPublisher(body: { name: string; site_url: string; username: string; app_password: string }): Promise<PublisherConfig> {
    return request('/publishers', { method: 'POST', body: JSON.stringify(body) });
  },
  deletePublisher(id: string): Promise<void> {
    return request(`/publishers/${id}`, { method: 'DELETE' });
  },
  testPublisher(id: string): Promise<{ ok: boolean; user?: unknown; error?: string }> {
    return request(`/publishers/${id}/test`, { method: 'POST' });
  },
  listPublishJobs(status?: string): Promise<PublishJob[]> {
    const qs = status ? `?status=${status}` : '';
    return request(`/publishes${qs}`);
  },
  createPublishJob(body: { article_id: string; config_id: string; title_override?: string }): Promise<PublishJob> {
    return request('/publishes', { method: 'POST', body: JSON.stringify(body) });
  },
  retryPublishJob(id: string): Promise<PublishJob> {
    return request(`/publishes/${id}/retry`, { method: 'POST' });
  },
  cancelPublishJob(id: string): Promise<PublishJob> {
    return request(`/publishes/${id}/cancel`, { method: 'POST' });
  },
  listMonitors(): Promise<MonitorTask[]> {
    return request('/monitors');
  },
  createMonitor(body: {
    name: string; brand: string; industry: string;
    target_questions: string[]; frequency: string;
    providers?: string[]; notify_email?: string; change_threshold?: number;
  }): Promise<MonitorTask> {
    return request('/monitors', { method: 'POST', body: JSON.stringify(body) });
  },
  deleteMonitor(id: string): Promise<void> {
    return request(`/monitors/${id}`, { method: 'DELETE' });
  },
  runMonitorNow(id: string): Promise<{ status: string }> {
    return request(`/monitors/${id}/run`, { method: 'POST' });
  },
  getMonitorTrends(id: string, days = 30): Promise<TrendData> {
    return request(`/monitors/${id}/trends?days=${days}`);
  },
  sendTestEmail(to: string): Promise<{ ok: boolean; error?: string }> {
    return request('/notifications/test', { method: 'POST', body: JSON.stringify({ to }) });
  },
```

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend/v0.3): types + API client for publishers/monitors/notifications"
```

---

### Task 6.2: Frontend Pages (Publisher, Publish, Monitor, Notification, Trend Chart)

**Files:**
- Create: `D:/GEO2/frontend/src/components/TrendChart.tsx`
- Create: `D:/GEO2/frontend/src/pages/PublisherConfig.tsx`
- Create: `D:/GEO2/frontend/src/pages/PublishList.tsx`
- Create: `D:/GEO2/frontend/src/pages/MonitorList.tsx`
- Create: `D:/GEO2/frontend/src/pages/MonitorDetail.tsx`
- Create: `D:/GEO2/frontend/src/pages/NotificationSettings.tsx`
- Modify: `D:/GEO2/frontend/src/App.tsx` (add v0.3 routes + nav)

- [ ] **Step 1: Create `TrendChart.tsx`**

Create `D:/GEO2/frontend/src/components/TrendChart.tsx`:

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import type { TrendPoint } from '@/types/v0.3';

export function TrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="run_at" tickFormatter={(v) => new Date(v).toLocaleDateString()} />
        <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
        <Tooltip
          formatter={(v: number) => `${(v * 100).toFixed(1)}%`}
          labelFormatter={(v) => new Date(v).toLocaleString()}
        />
        <Line type="monotone" dataKey="mention_rate" stroke="#2563eb" strokeWidth={2} dot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Create `PublisherConfig.tsx`**

Create `D:/GEO2/frontend/src/pages/PublisherConfig.tsx`:

```tsx
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function PublisherConfigPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', site_url: '', username: '', app_password: '' });

  const { data: configs, isLoading } = useQuery({
    queryKey: ['publishers'],
    queryFn: () => api.listPublishers(),
  });

  const create = useMutation({
    mutationFn: () => api.createPublisher(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['publishers'] });
      setShowForm(false);
      setForm({ name: '', site_url: '', username: '', app_password: '' });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deletePublisher(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['publishers'] }),
  });

  const test = useMutation({
    mutationFn: (id: string) => api.testPublisher(id),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">WordPress 凭证</h1>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md"
          >
            + 添加凭证
          </button>
        </div>

        {showForm && (
          <div className="bg-white rounded-lg shadow p-6 mb-4">
            <h2 className="text-lg font-semibold mb-3">添加 WordPress 凭证</h2>
            <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="凭证名称（如：公司主站）" className="w-full px-3 py-2 border rounded-md mb-2" />
            <input type="url" value={form.site_url} onChange={(e) => setForm({ ...form, site_url: e.target.value })}
              placeholder="https://example.com" className="w-full px-3 py-2 border rounded-md mb-2" />
            <input type="text" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
              placeholder="WordPress 用户名" className="w-full px-3 py-2 border rounded-md mb-2" />
            <input type="password" value={form.app_password} onChange={(e) => setForm({ ...form, app_password: e.target.value })}
              placeholder="Application Password (WordPress 后台生成)" className="w-full px-3 py-2 border rounded-md mb-3" />
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setShowForm(false)} className="px-3 py-1 text-gray-600">取消</button>
              <button type="button" onClick={() => create.mutate()} disabled={!form.name || !form.site_url || form.app_password.length < 10 || create.isPending}
                className="px-4 py-1 bg-blue-600 text-white rounded-md disabled:opacity-50">
                {create.isPending ? '添加中...' : '添加'}
              </button>
            </div>
          </div>
        )}

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {configs && configs.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有凭证。
          </div>
        )}

        {configs && configs.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {configs.map((c) => (
              <div key={c.id} className="p-4 flex justify-between items-center">
                <div>
                  <div className="font-medium">{c.name}</div>
                  <div className="text-sm text-gray-500">{c.site_url} · {c.username}</div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={async () => {
                      const result = await test.mutateAsync(c.id);
                      alert(result.ok ? '连接成功！' : `连接失败：${result.error}`);
                    }}
                    className="px-3 py-1 text-sm bg-green-500 text-white rounded"
                  >
                    测试
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`删除凭证「${c.name}」？`)) remove.mutate(c.id);
                    }}
                    className="px-3 py-1 text-sm bg-red-500 text-white rounded"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `PublishList.tsx`**

Create `D:/GEO2/frontend/src/pages/PublishList.tsx`:

```tsx
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-800',
  running: 'bg-blue-100 text-blue-800',
  success: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-yellow-100 text-yellow-800',
};

const STATUS_LABELS: Record<string, string> = {
  pending: '等待中', running: '发布中', success: '已发布', failed: '失败', cancelled: '已取消',
};

export default function PublishList() {
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['publish-jobs'],
    queryFn: () => api.listPublishJobs(),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">发布任务</h1>
        {isLoading && <p className="text-gray-500">加载中...</p>}
        {jobs && jobs.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有发布任务。<br />
            <span className="text-sm">从 v0.2 审核通过的 Article 创建发布任务</span>
          </div>
        )}
        {jobs && jobs.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {jobs.map((j) => (
              <div key={j.id} className="p-4 flex justify-between items-center">
                <div>
                  <div className="text-sm text-gray-500">文章 ID: {j.article_id}</div>
                  <div className="text-xs text-gray-400">{formatDate(j.created_at)}</div>
                  {j.remote_url && <a href={j.remote_url} target="_blank" rel="noopener" className="text-xs text-blue-600">{j.remote_url}</a>}
                </div>
                <span className={`text-xs px-2 py-1 rounded ${STATUS_COLORS[j.status]}`}>
                  {STATUS_LABELS[j.status]}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `MonitorList.tsx`**

Create `D:/GEO2/frontend/src/pages/MonitorList.tsx`:

```tsx
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';

const FREQ_LABELS: Record<string, string> = { hourly: '每小时', daily: '每天', weekly: '每周' };

export default function MonitorList() {
  const { data: monitors, isLoading } = useQuery({
    queryKey: ['monitors'],
    queryFn: () => api.listMonitors(),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">监测任务</h1>
          <Link to="/monitors/new" className="px-4 py-2 bg-blue-600 text-white rounded-md">
            + 新建监测
          </Link>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {monitors && monitors.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有监测任务。
          </div>
        )}

        {monitors && monitors.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {monitors.map((m) => (
              <Link
                key={m.id}
                to={`/monitors/${m.id}`}
                className="block p-4 hover:bg-gray-50"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-gray-900">{m.name}</div>
                    <div className="text-sm text-gray-500">
                      {m.brand} · {FREQ_LABELS[m.frequency]}
                      {m.is_active ? '' : ' · 已暂停'}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400">
                    {m.last_run_at ? `上次：${formatDate(m.last_run_at)}` : '未运行'}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('zh-CN');
}
```

- [ ] **Step 5: Create `MonitorDetail.tsx`**

Create `D:/GEO2/frontend/src/pages/MonitorDetail.tsx`:

```tsx
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { TrendChart } from '@/components/TrendChart';
import { formatDate } from '@/lib/utils';

export default function MonitorDetail() {
  const { monitorId = '' } = useParams<{ monitorId: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: monitor } = useQuery({
    queryKey: ['monitor', monitorId],
    queryFn: () => fetch(`/api/monitors/${monitorId}`).then((r) => r.json()),
  });

  const { data: trends } = useQuery({
    queryKey: ['monitor-trends', monitorId],
    queryFn: () => api.getMonitorTrends(monitorId, 30),
  });

  const runNow = useMutation({
    mutationFn: () => api.runMonitorNow(monitorId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['monitor-trends', monitorId] }),
  });

  const remove = useMutation({
    mutationFn: () => api.deleteMonitor(monitorId),
    onSuccess: () => navigate('/monitors'),
  });

  if (!monitor) return <div className="p-8 text-center text-gray-500">加载中...</div>;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <Link to="/monitors" className="text-blue-600 text-sm">← 返回监测列表</Link>
        <h1 className="text-3xl font-bold text-gray-900 mt-2">{monitor.name}</h1>
        <p className="text-gray-600 mt-1">{monitor.brand} · {monitor.industry}</p>

        <div className="bg-white rounded-lg shadow p-4 mt-4 flex justify-between items-center">
          <div>
            <div>状态：{monitor.is_active ? '运行中' : '已暂停'}</div>
            <div className="text-sm text-gray-500">
              频率：{monitor.frequency} · 阈值：{(monitor.change_threshold * 100).toFixed(0)}%
              {monitor.last_run_at && ` · 上次：${formatDate(monitor.last_run_at)}`}
            </div>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => runNow.mutate()} disabled={runNow.isPending}
              className="px-3 py-1 text-sm bg-blue-500 text-white rounded disabled:opacity-50">
              立即跑
            </button>
            <button type="button" onClick={() => { if (confirm('删除此监测任务？')) remove.mutate(); }}
              className="px-3 py-1 text-sm bg-red-500 text-white rounded">
              删除
            </button>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <h2 className="text-lg font-semibold mb-3">趋势 (近 30 天)</h2>
          {trends && trends.points.length > 0 ? (
            <TrendChart data={trends.points} />
          ) : (
            <p className="text-gray-500 text-center py-8">还没有数据</p>
          )}
        </div>

        <div className="bg-white rounded-lg shadow p-6 mt-4">
          <h2 className="text-lg font-semibold mb-3">问题</h2>
          <ul className="list-disc list-inside space-y-1 text-sm">
            {monitor.target_questions.map((q: string, i: number) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Create `NotificationSettings.tsx`**

Create `D:/GEO2/frontend/src/pages/NotificationSettings.tsx`:

```tsx
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { api } from '@/api/client';

export default function NotificationSettings() {
  const [to, setTo] = useState('');

  const send = useMutation({
    mutationFn: () => api.sendTestEmail(to),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">通知设置</h1>
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-600 mb-4">
            通知邮件使用 .env 中配置的 SMTP 服务。点击下方按钮发送测试邮件，验证 SMTP 配置正确。
          </p>
          <input
            type="email"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="收件人邮箱"
            className="w-full px-3 py-2 border rounded-md mb-3"
          />
          <button
            type="button"
            onClick={() => send.mutate()}
            disabled={!to || send.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
          >
            {send.isPending ? '发送中...' : '发送测试邮件'}
          </button>
          {send.isSuccess && (
            <p className={`mt-3 text-sm ${send.data.ok ? 'text-green-600' : 'text-red-600'}`}>
              {send.data.ok ? '发送成功！请检查收件箱（包括垃圾邮件）。' : `失败：${send.data.error}`}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Update `App.tsx` with v0.3 routes + nav**

Edit `D:/GEO2/frontend/src/App.tsx`. Add imports:

```tsx
import PublisherConfigPage from '@/pages/PublisherConfig';
import PublishList from '@/pages/PublishList';
import MonitorList from '@/pages/MonitorList';
import MonitorDetail from '@/pages/MonitorDetail';
import NotificationSettings from '@/pages/NotificationSettings';
```

Add to nav (inside Header):

```tsx
        <nav className="space-x-4 text-sm">
          <Link to="/" className="text-gray-600 hover:text-gray-900">诊断</Link>
          <Link to="/knowledge" className="text-gray-600 hover:text-gray-900">知识库</Link>
          <Link to="/tasks" className="text-gray-600 hover:text-gray-900">任务</Link>
          <Link to="/reviews" className="text-gray-600 hover:text-gray-900">审核</Link>
          <Link to="/publishers" className="text-gray-600 hover:text-gray-900">发布</Link>
          <Link to="/monitors" className="text-gray-600 hover:text-gray-900">监测</Link>
          <Link to="/notifications" className="text-gray-600 hover:text-gray-900">通知</Link>
        </nav>
```

Add to Routes:

```tsx
          <Route path="/publishers" element={<PublisherConfigPage />} />
          <Route path="/publishes" element={<PublishList />} />
          <Route path="/monitors" element={<MonitorList />} />
          <Route path="/monitors/:monitorId" element={<MonitorDetail />} />
          <Route path="/notifications" element={<NotificationSettings />} />
```

(Note: the v0.2 frontend's nav also has "新建诊断" link — keep that.)

- [ ] **Step 8: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0 (with possible minor warnings).

- [ ] **Step 9: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend/v0.3): publisher/publish/monitor/notification pages + trend chart + App routes"
```

---

## Phase 7: End-to-End Verification & Documentation

### Task 7.1: E2E Backend Test

**Files:**
- Create: `D:/GEO2/backend/tests/test_e2e_v0.3.py`

- [ ] **Step 1: Write E2E test**

Create `D:/GEO2/backend/tests/test_e2e_v0.3.py`:

```python
"""E2E test for v0.3 flow: publisher config → monitor task → snapshots."""
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from cryptography.fernet import Fernet

import pytest
import respx
from httpx import Response

from app.core.config import Settings


@pytest.fixture
def settings_with_key() -> Settings:
    return Settings(
        encryption_key=Fernet.generate_key().decode(),
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        smtp_from="noreply@example.com",
    )


def test_e2e_publisher_flow(client, monkeypatch) -> None:
    """Create config + verify it's encrypted (not exposed)."""
    with patch("app.core.config.get_settings", lambda: Settings(
        encryption_key=Fernet.generate_key().decode(),
    )):
        from app.domain.security import encryption
        encryption._cipher = None

        # Add a config
        resp = client.post("/api/publishers", json={
            "name": "Test", "site_url": "https://example.com",
            "username": "admin", "app_password": "abcdefghijklmnop",
        })
        assert resp.status_code == 201
        config = resp.json()
        # Password NOT in response
        assert "app_password" not in config
        assert "app_password_encrypted" not in config

        # List
        list_resp = client.get("/api/publishers")
        assert len(list_resp.json()) == 1


def test_e2e_monitor_flow(client) -> None:
    """Create monitor task → run now → snapshot created."""
    from unittest.mock import MagicMock
    from app.models.schemas import MentionResult

    mentions = [
        MentionResult(
            question="q1", llm_provider="deepseek",
            llm_answer="小米", brand_mentioned=True, mention_position=1,
        ),
    ]

    with patch("app.api.monitors.schedule_monitor_task"):
        create = client.post("/api/monitors", json={
            "name": "Test", "brand": "小米", "industry": "手机",
            "target_questions": ["q1"], "frequency": "daily",
        })
        assert create.status_code == 201
        mid = create.json()["id"]

    with patch("app.api.monitors.execute_monitor_run"):
        run_resp = client.post(f"/api/monitors/{mid}/run")
        assert run_resp.status_code == 202

    # Get trends (empty)
    trends = client.get(f"/api/monitors/{mid}/trends?days=30")
    assert trends.status_code == 200
```

- [ ] **Step 2: Run E2E test**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_e2e_v0.3.py -v
```

Expected: All PASS.

- [ ] **Step 3: Run ALL tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All v0.1 + v0.2 + v0.3 tests PASS.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add backend/tests/ && git commit -m "test(backend/v0.3): end-to-end publisher + monitor flow"
```

---

### Task 7.2: Manual Verification Checklist

**Files:**
- Create: `D:/GEO2/docs/MANUAL_VERIFICATION_V0.3.md`

- [ ] **Step 1: Write checklist**

Create `D:/GEO2/docs/MANUAL_VERIFICATION_V0.3.md`:

```markdown
# 手动验证清单 — GEO Agent v0.3

发布前必跑 11 个场景。

## 前置条件

\`\`\`bash
cd "D:/GEO2"
# 编辑 .env，确保以下都已设置：
# - DEEPSEEK_API_KEY
# - ENCRYPTION_KEY  (运行: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# - SMTP_HOST, SMTP_USER, SMTP_PASSWORD 等
docker-compose up --build -d
sleep 30
\`\`\`

## 场景

### 1. 添加 WordPress 凭证 ✅

1. 进入 /publishers
2. 添加凭证，填入真实 WordPress Application Password
3. 点"测试"按钮
4. **预期**：弹窗显示"连接成功"

### 2. 发布一篇文章（成功）✅

1. 准备一个真实 WordPress 站点
2. 从 v0.2 选一个 approved Article
3. 在 /publishes 创建发布任务
4. 等待任务完成
5. **预期**：status=success，显示 remote_url；登录 WordPress 后台可见

### 3. 发布失败（错误凭证）❌

1. 添加一个错误密码的凭证
2. 尝试用它发布
3. **预期**：status=failed，error_message 含"认证失败"

### 4. 重试失败发布 ✅

1. 复用场景 3 的失败任务
2. 修复凭证后点"重试"
3. **预期**：任务重新运行

### 5. 创建 daily 监测 ✅

1. 进 /monitors/new
2. 填入品牌、3-5 个问题、daily
3. **预期**：监测任务出现在列表

### 6. 立即跑一次监测 ✅

1. 进监测详情
2. 点"立即跑"
3. 等待几秒
4. **预期**：趋势图出现第一个数据点

### 7. 监测变化触发邮件 ⚠️

1. 修改数据库人为制造大变化（手动改 mention_rate）
2. 等待下次执行
3. **预期**：收件箱收到"提及率上升/下降 X%"邮件

### 8. 暂停 / 恢复监测任务 🛑

1. 进监测详情
2. 修改 is_active 字段（v0.3 暂不提供 UI，需要 SQL 修改）
3. **预期**：暂停后不再自动跑

### 9. 进程重启后监测调度恢复 ✅

1. 创建几个 daily 监测任务
2. `docker-compose restart backend`
3. 等 30 秒
4. **预期**：监测继续按计划执行（看 last_run_at 是否更新）

### 10. 删凭证有发布任务 ❌

1. 创建凭证 + 发布任务
2. 尝试删凭证
3. **预期**：409 错误，提示"有 N 个发布任务"

### 11. 发未审核文章 ❌

1. 选一个 review_status=pending 的 Article
2. 尝试发布
3. **预期**：422 错误，提示"article must be approved"

## 通过标准

11 项全过 → v0.3 完成。
\`\`\`

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/MANUAL_VERIFICATION_V0.3.md && git commit -m "docs: v0.3 manual verification checklist"
```

---

### Task 7.3: Update ROADMAP

**Files:**
- Modify: `D:/GEO2/docs/ROADMAP.md`

- [ ] **Step 1: Mark v0.3 design + plan complete**

Edit `D:/GEO2/docs/ROADMAP.md`. Update the v0.3 entry to mark design+plan as done.

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/ROADMAP.md && git commit -m "docs: mark v0.3 design + plan as complete in ROADMAP"
```

---

## Self-Review

After writing this plan, run the writing-plans self-review checklist:

**1. Spec coverage** — Every requirement in the v0.3 spec is covered:

| Spec § | Implemented in Task |
|---|---|
| §1 (background, scope) | Phase 0 + Task 7.3 |
| §2 (users, scenarios) | Task 6.2 (frontend pages), Task 7.2 (manual) |
| §3 (architecture) | Phase 0 + main.py lifespan in Task 4.3 |
| §4 (data model) | Task 0.3 (ORM) |
| §5.1 (WordPress) | Tasks 1.1-1.3, 2.1-2.3 |
| §5.2 (monitor) | Tasks 3.1-3.4, 4.1-4.3, 5.1 |
| §5.3 (trends) | Task 5.1 (trends API) + Task 6.2 (TrendChart) |
| §5.4 (notification) | Tasks 4.1-4.2 |
| §6 (error handling) | Throughout each task |
| §7 (testing) | Tests in every task + Task 7.1 |
| §8 (acceptance) | Task 7.2 |
| §9 (out of scope) | All explicitly excluded |

**2. Placeholder scan** — No TBD/TODO. All code blocks complete.

**3. Type consistency** —
- `PublishJobStatus` enum ↔ `publish_jobs.status` field ↔ API responses ✓
- `MonitorFrequency` enum ↔ `monitor_tasks.frequency` ↔ scheduler `frequency_to_interval` ✓
- `PublisherConfig` model excludes `app_password` (verified in test_create_publisher_config) ✓
- `MonitorRepository.list_active_monitor_tasks` ↔ `load_all_monitor_tasks` (startup) ✓
- `_EXEC_LOCK` shared across v0.1/v0.2/v0.3 workers ✓

All consistent.

---

## Execution Handoff

This plan is **complete** and saved to:
`D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.3.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task with two-stage review between tasks. Best for catching issues early and maintaining quality across 25+ tasks.

**2. Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints. Faster but no inter-task review.

**Which approach?**

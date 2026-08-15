"""Shared pytest fixtures."""
import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient  # noqa: F401
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all v0.x ORM models at module load so Base.metadata sees their tables
# before any fixture calls Base.metadata.create_all. This is required for
# v0.4 (agent_sessions / agent_messages) tables to exist in tests.
from app.models import orm as _orm_v01  # noqa: F401
try:
    from app.models import orm_v02 as _orm_v02  # noqa: F401
except ImportError:
    pass
try:
    from app.models import orm_v03 as _orm_v03  # noqa: F401
except ImportError:
    pass
try:
    from app.models import orm_v04 as _orm_v04  # noqa: F401
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest_asyncio.fixture
async def temp_db() -> AsyncGenerator[str, None]:
    """Provide a temporary SQLite database URL and clean up after."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    yield url
    # Windows: file may still be held briefly after async teardown.
    for _ in range(5):
        if not os.path.exists(path):
            break
        try:
            os.remove(path)
            break
        except PermissionError:
            import time
            time.sleep(0.1)


@pytest_asyncio.fixture
async def db_session(temp_db: str, monkeypatch) -> AsyncGenerator[AsyncSession, None]:
    """Provide an initialized DB with schema and a session bound to it."""
    from cryptography.fernet import Fernet
    from sqlalchemy import event
    from app.core.config import get_settings
    from app.core.db import init_db
    from app.models.orm import Base

    # v0.3 — encryption required by PublisherConfigORM tests.
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    # Settings now requires a non-empty DEEPSEEK_API_KEY unless
    # GEO_ALLOW_MISSING_LLM_KEY=1; tests don't actually call the LLM, so
    # any non-empty value suffices.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app.domain.security import encryption
    encryption._cipher = None
    encryption._settings = None

    # Import all v0.x ORM models so Base.metadata sees them BEFORE create_all.
    # Without this, v0.4 tables (agent_sessions/agent_messages) won't be created.
    from app.models import orm as _orm_v01  # noqa: F401
    try:
        from app.models import orm_v02 as _orm_v02  # noqa: F401
    except ImportError:
        pass
    try:
        from app.models import orm_v03 as _orm_v03  # noqa: F401
    except ImportError:
        pass
    try:
        from app.models import orm_v04 as _orm_v04  # noqa: F401
    except ImportError:
        pass

    # Import all v0.x ORM models so Base.metadata sees them BEFORE create_all.
    # Without this, v0.4 tables (agent_sessions/agent_messages) won't be created.
    from app.models import orm as _orm_v01  # noqa: F401
    try:
        from app.models import orm_v02 as _orm_v02  # noqa: F401
    except ImportError:
        pass
    try:
        from app.models import orm_v03 as _orm_v03  # noqa: F401
    except ImportError:
        pass
    try:
        from app.models import orm_v04 as _orm_v04  # noqa: F401
    except ImportError:
        pass

    engine = create_async_engine(temp_db)

    # Enable SQLite foreign key cascade enforcement (needed for ON DELETE CASCADE)
    if temp_db.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_fk(dbapi_conn, _conn_record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Replace the global _session_factory so code that calls get_session_factory()
    # (e.g. monitor_service, publish_worker) uses our test engine.
    import app.core.db
    monkeypatch.setattr(app.core.db, "_session_factory", session_factory, raising=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_memory_vectors():
    """Phase 2:mock 记忆向量依赖(EmbeddingService + MemoryVectorIndex)。

    杜绝测试真加载 bge(沙箱无外网会卡死)/写真 ChromaDB。默认 embed 返回假向量、
    向量库为空。需要精确控制的用例可在自己的 with patch(...) 里覆盖。
    非 autouse:仅 MemoryService/react_loop 记忆集成测试通过 autouse 桩引用它,
    test_memory_vector.py 测真 ChromaDB 不受影响。
    """
    from unittest.mock import patch

    with patch("app.domain.agent.memory.EmbeddingService") as MockEmb, \
         patch("app.domain.agent.memory.MemoryVectorIndex") as MockVidx:
        MockEmb.embed.side_effect = lambda texts: [[1.0] + [0.0] * 511 for _ in texts]
        MockVidx.return_value.ids_in_scope.return_value = set()
        MockVidx.return_value.query.return_value = []
        yield MockEmb, MockVidx


@pytest.fixture
def client(temp_db: str, monkeypatch) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with isolated test DB."""
    from cryptography.fernet import Fernet
    from app.core.config import get_settings
    from app.main import create_app

    # Override DB URL + ENCRYPTION_KEY before app creates engine / encrypts anything
    monkeypatch.setenv("DATABASE_URL", temp_db)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    # Settings now requires a non-empty DEEPSEEK_API_KEY unless
    # GEO_ALLOW_MISSING_LLM_KEY=1; tests don't actually call the LLM, so
    # any non-empty value suffices.
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-not-used")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    app = create_app()
    with TestClient(app) as c:
        yield c

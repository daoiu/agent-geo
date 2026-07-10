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

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest_asyncio.fixture
async def temp_db() -> AsyncGenerator[str, None]:
    """Provide a temporary SQLite database URL and clean up after."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"
    yield url
    if os.path.exists(path):
        os.remove(path)


@pytest_asyncio.fixture
async def db_session(temp_db: str) -> AsyncGenerator[AsyncSession, None]:
    """Provide an initialized DB with schema and a session bound to it."""
    from app.core.db import init_db
    from app.models.orm import Base

    engine = create_async_engine(temp_db)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def client(temp_db: str, monkeypatch) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with isolated test DB."""
    from app.core.config import get_settings
    from app.main import create_app

    # Override DB URL before app creates engine
    monkeypatch.setenv("DATABASE_URL", temp_db)
    get_settings.cache_clear()  # type: ignore[attr-defined]

    app = create_app()
    with TestClient(app) as c:
        yield c

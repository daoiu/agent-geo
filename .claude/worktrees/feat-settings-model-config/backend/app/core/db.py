"""Database engine and session management."""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.models.orm import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Lazy-init singleton engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
        )
        # Enable SQLite foreign key cascade enforcement
        if settings.database_url.startswith("sqlite"):

            @event.listens_for(_engine.sync_engine, "connect")
            def _enable_sqlite_fk(dbapi_conn, _conn_record):  # noqa: ANN001
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazy-init session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


async def init_db() -> None:
    """Create tables. Idempotent — safe to call multiple times."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # v0.5 — in-place migration: add pending_index to existing knowledge_chunks
    # (create_all doesn't add columns to existing tables)
    await _migrate_v05_add_pending_index()


async def _migrate_v05_add_pending_index() -> None:
    """Add knowledge_chunks.pending_index to existing DBs (no-op if already present)."""
    from sqlalchemy import text
    engine = get_engine()
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("PRAGMA table_info(knowledge_chunks)"))
        columns = {row[1] for row in result.fetchall()}
        if "pending_index" not in columns:
            await conn.execute(
                text("ALTER TABLE knowledge_chunks ADD COLUMN pending_index BOOLEAN NOT NULL DEFAULT 0")
            )


async def dispose_db() -> None:
    """Clean shutdown — release connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None

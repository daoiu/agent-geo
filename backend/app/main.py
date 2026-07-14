"""FastAPI application factory."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_chat, agent_sessions, articles, diagnosis, knowledge, monitors, notifications, publishers, reports, reviews, tasks
from app.core.config import get_settings
from app.core.db import dispose_db, init_db
from app.core.sentry_init import init_sentry_from_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App startup + shutdown."""
    # v0.6+ P1#17（Task 18）：Sentry 异常聚合接入
    # SENTRY_DSN 缺失时静默 no-op,不阻塞启动
    sentry_initialized = init_sentry_from_settings()
    if sentry_initialized:
        logger.info("sentry_initialized")
    else:
        logger.info("sentry_skipped_dsn_missing")

    await init_db()
    # v0.3 — start monitor scheduler and reload active tasks from DB
    from app.domain.monitor.scheduler import (
        load_all_monitor_tasks,
        shutdown_scheduler,
        start_scheduler,
    )
    start_scheduler()
    await load_all_monitor_tasks()
    # v0.5 — lazy reindex of existing chunks into ChromaDB
    from app.services.reindex import ReindexService
    reindex_stats = await ReindexService().reindex_all()
    logger.info("v0.5_reindex_done", **reindex_stats)
    yield
    shutdown_scheduler()
    await dispose_db()


def create_app() -> FastAPI:
    """Build the FastAPI app."""
    settings = get_settings()
    app = FastAPI(
        title="GEO Optimization Agent",
        version="0.1.0",
        description="白帽 GEO 诊断工具",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(diagnosis.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(articles.router, prefix="/api")
    app.include_router(reviews.router, prefix="/api")
    app.include_router(publishers.configs_router, prefix="/api")
    app.include_router(publishers.jobs_router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(monitors.router, prefix="/api")
    app.include_router(agent_sessions.router, prefix="/api")
    app.include_router(agent_chat.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

"""FastAPI application factory."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent_chat, agent_sessions, diagnosis, knowledge, monitors, notifications, publishers, reports, reviews, tasks
from app.core.config import get_settings
from app.core.db import dispose_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App startup + shutdown."""
    await init_db()
    # v0.3 — start monitor scheduler and reload active tasks from DB
    from app.domain.monitor.scheduler import (
        load_all_monitor_tasks,
        shutdown_scheduler,
        start_scheduler,
    )
    start_scheduler()
    await load_all_monitor_tasks()
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

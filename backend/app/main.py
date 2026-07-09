"""FastAPI application factory."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api import diagnosis, reports
from app.core.config import get_settings
from app.core.db import dispose_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App startup + shutdown."""
    await init_db()
    yield
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

    app.include_router(diagnosis.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

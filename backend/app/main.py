"""FastAPI application entry point."""
from fastapi import FastAPI

app = FastAPI(
    title="GEO Optimization Agent",
    version="0.1.0",
    description="白帽 GEO 诊断工具",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}

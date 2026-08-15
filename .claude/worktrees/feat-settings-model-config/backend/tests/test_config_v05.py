"""Tests for v0.5 settings additions."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.core.config import Settings


def test_v05_settings_have_defaults() -> None:
    s = Settings()
    assert s.chroma_path == "./data/chroma"
    assert s.models_cache_dir == "./data/models"
    assert s.embedding_batch_size == 50
    assert s.hybrid_top_k_vector == 20
    assert s.hybrid_top_k_keyword == 20
    assert s.hybrid_rrf_k == 60


def test_settings_loads_env_file_from_project_root() -> None:
    """Regression: env_file must be anchored to project root, not CWD.

    The project keeps `.env` at the repo root (per docker-compose.yml).
    Before the fix, running `uvicorn` from `backend/` would NOT pick up
    that .env, causing ``deepseek_api_key=""`` and the OpenAI client to
    send ``Authorization: Bearer `` (illegal header).

    We assert this by spawning a fresh interpreter with CWD=backend/ and
    reading what ``Settings()`` actually loads — independent of pytest's
    own CWD or any module-level caches.
    """
    project_root = Path(__file__).resolve().parents[2]
    backend = project_root / "backend"
    assert backend.is_dir(), f"backend dir not found at {backend}"

    result = subprocess.run(
        [
            "python",
            "-c",
            (
                "from app.core.config import Settings; "
                "s = Settings(); "
                "print('LOADED' if s.deepseek_api_key else 'EMPTY')"
            ),
        ],
        cwd=str(backend),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(backend)},
        timeout=30,
    )
    assert result.returncode == 0, (
        f"subprocess failed.\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "LOADED" in result.stdout, (
        "Settings() returned empty deepseek_api_key when CWD=backend/. "
        "env_file is being resolved against CWD instead of project root.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
# GEO Optimization Agent v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Web app that diagnoses a brand's GEO (Generative Engine Optimization) health by crawling its website, querying 1-2 Chinese LLMs (DeepSeek/Kimi), and producing a 5-dimension scorecard with actionable suggestions plus a downloadable PDF.

**Architecture:** Monolithic FastAPI (asyncio background tasks) + SQLite + React/Vite SPA + docker-compose. Reports rendered by React on client; PDFs generated server-side via WeasyPrint from Jinja2 templates. Single-machine deployment, no auth in MVP.

**Tech Stack:** Python 3.11+, FastAPI 0.115+, httpx, selectolax, openai SDK (DeepSeek/Kimi compatible), SQLAlchemy 2.0 async + aiosqlite, Pydantic v2, WeasyPrint, Jinja2, pytest + pytest-asyncio. React 18 + TypeScript + Vite, React Router 6, Tailwind CSS + shadcn/ui, Recharts, TanStack Query. Docker + docker-compose.

## Global Constraints

These apply to **every** task. Each task's requirements implicitly include this section.

- Python 3.11+ syntax (e.g. `X | None`, `list[X]`, `match` statements where useful)
- All backend code is `async`/`await` — no blocking I/O on the request path
- All Pydantic models use `model_config = ConfigDict(from_attributes=True)` where ORM interop is needed
- All times stored as UTC; UI converts to local
- All money/numeric scores use `float`; never use `Decimal` (out of MVP scope)
- All HTTP timeouts: 10s for crawl, 30s for LLM call, 90s total per diagnosis
- All file paths in this plan are relative to `D:/GEO2/` unless absolute
- All commits use Conventional Commits: `feat:`, `fix:`, `test:`, `chore:`, `docs:`
- Tests live next to source under `tests/` mirroring source layout
- TDD discipline: every code-writing task starts with a failing test
- No emoji in code, comments, or commit messages (UI text only, after product review)
- English in code/comments; Simplified Chinese in user-facing strings (per project language rule)

**Reference spec:** `docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md` — re-read sections as needed.

---

## Phase 0: Project Scaffolding

### Task 0.1: Project Root + .gitignore

**Files:**
- Create: `D:/GEO2/.gitignore`
- Create: `D:/GEO2/README.md`
- Create: `D:/GEO2/.env.example`

- [ ] **Step 1: Create `.gitignore`**

Create `D:/GEO2/.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
env/
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/

# Node
node_modules/
.vite/
dist/
.tsbuildinfo
*.log

# IDE
.idea/
.vscode/
*.swp
*.swo
.DS_Store
Thumbs.db

# Project runtime
backend/data/reports.db
backend/data/reports/*.pdf
*.local

# Environment
.env
.env.local
.env.*.local

# OS
.DS_Store
```

- [ ] **Step 2: Create `.env.example`**

Create `D:/GEO2/.env.example`:

```bash
# DeepSeek API (https://platform.deepseek.com/)
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# Kimi API (https://platform.moonshot.cn/) - optional
KIMI_API_KEY=
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k

# Which providers to enable (comma-separated)
LLM_PROVIDERS=deepseek

# App
APP_PORT=8000
APP_HOST=0.0.0.0
DATABASE_URL=sqlite+aiosqlite:///./data/reports.db
LOG_LEVEL=INFO

# Diagnosis limits
DIAGNOSIS_TOTAL_TIMEOUT_S=90
LLM_CALL_TIMEOUT_S=30
CRAWL_TIMEOUT_S=10
```

- [ ] **Step 3: Create minimal `README.md`**

Create `D:/GEO2/README.md`:

```markdown
# GEO Optimization Agent

白帽 GEO (生成引擎优化) 诊断工具。输入品牌信息 → 自动生成 GEO 健康度诊断报告。

## 快速开始

\`\`\`bash
# 1. 复制环境变量模板并填入 API key
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY

# 2. 启动服务
docker-compose up --build

# 3. 访问
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000
# API 文档: http://localhost:8000/docs
\`\`\`

## 文档

- 设计文档: `docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md`
- 实施计划: `docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md`

## 开发

参见实施计划中的 task-by-task 步骤。
```

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add .gitignore .env.example README.md && git commit -m "chore: initialize project root with .gitignore, .env.example, README"
```

---

### Task 0.2: Backend FastAPI Skeleton + Health Check (TDD)

**Files:**
- Create: `D:/GEO2/backend/requirements.txt`
- Create: `D:/GEO2/backend/pyproject.toml`
- Create: `D:/GEO2/backend/app/__init__.py`
- Create: `D:/GEO2/backend/app/main.py`
- Create: `D:/GEO2/backend/tests/__init__.py`
- Create: `D:/GEO2/backend/tests/test_health.py`
- Create: `D:/GEO2/backend/data/.gitkeep`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `app.main:app` (FastAPI app instance)

- [ ] **Step 1: Create `requirements.txt`**

Create `D:/GEO2/backend/requirements.txt`:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.1
httpx==0.28.1
selectolax==0.3.21
openai==1.60.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
weasyprint==63.1
jinja2==3.1.5
python-multipart==0.0.20
structlog==24.4.0
pytest==8.3.4
pytest-asyncio==0.25.0
pytest-cov==6.0.0
httpx==0.28.1
```

- [ ] **Step 2: Create `pyproject.toml`**

Create `D:/GEO2/backend/pyproject.toml`:

```toml
[project]
name = "geo-agent-backend"
version = "0.1.0"
description = "GEO optimization agent backend"
requires-python = ">=3.11"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["app"]
omit = ["tests/*", "data/*"]
```

- [ ] **Step 3: Create empty package files**

Create empty files:
- `D:/GEO2/backend/app/__init__.py` (empty)
- `D:/GEO2/backend/tests/__init__.py` (empty)
- `D:/GEO2/backend/data/.gitkeep` (empty)

- [ ] **Step 4: Create `app/main.py` with minimal FastAPI app**

Create `D:/GEO2/backend/app/main.py`:

```python
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
```

- [ ] **Step 5: Write failing test**

Create `D:/GEO2/backend/tests/test_health.py`:

```python
"""Tests for the health check endpoint."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    """GET /health returns 200 and {'status': 'ok'}."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_does_not_require_auth() -> None:
    """Health check has no auth requirements."""
    response = client.get("/health", headers={})
    assert response.status_code == 200
```

- [ ] **Step 6: Install dependencies and run test**

```bash
cd "D:/GEO2/backend" && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt && pytest tests/test_health.py -v
```

Expected: Both tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): scaffold FastAPI app with health check endpoint"
```

---

### Task 0.3: Frontend React + Vite Skeleton

**Files:**
- Create: `D:/GEO2/frontend/package.json`
- Create: `D:/GEO2/frontend/vite.config.ts`
- Create: `D:/GEO2/frontend/tsconfig.json`
- Create: `D:/GEO2/frontend/tsconfig.node.json`
- Create: `D:/GEO2/frontend/index.html`
- Create: `D:/GEO2/frontend/tailwind.config.js`
- Create: `D:/GEO2/frontend/postcss.config.js`
- Create: `D:/GEO2/frontend/src/main.tsx`
- Create: `D:/GEO2/frontend/src/App.tsx`
- Create: `D:/GEO2/frontend/src/index.css`
- Create: `D:/GEO2/frontend/src/vite-env.d.ts`

**Interfaces:**
- Consumes: nothing
- Produces: dev server at http://localhost:5173 showing placeholder page

- [ ] **Step 1: Create `package.json`**

Create `D:/GEO2/frontend/package.json`:

```json
{
  "name": "geo-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "@tanstack/react-query": "^5.62.0",
    "recharts": "^2.15.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.5"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.0.3",
    "tailwindcss": "^3.4.16",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20"
  }
}
```

- [ ] **Step 2: Create `vite.config.ts`**

Create `D:/GEO2/frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 3: Create `tsconfig.json`**

Create `D:/GEO2/frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

Create `D:/GEO2/frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create `index.html`**

Create `D:/GEO2/frontend/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GEO 诊断 Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create Tailwind config**

Create `D:/GEO2/frontend/tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

Create `D:/GEO2/frontend/postcss.config.js`:

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 6: Create source files**

Create `D:/GEO2/frontend/src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
}
```

Create `D:/GEO2/frontend/src/vite-env.d.ts`:

```typescript
/// <reference types="vite/client" />
```

Create `D:/GEO2/frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Create `D:/GEO2/frontend/src/App.tsx`:

```tsx
export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          GEO 诊断 Agent
        </h1>
        <p className="text-gray-600">脚手架就绪 - 等待功能开发</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Install dependencies and verify dev server starts**

```bash
cd "D:/GEO2/frontend" && npm install
```

Then in a separate terminal:

```bash
cd "D:/GEO2/frontend" && npm run dev
```

Expected: Vite reports `Local: http://localhost:5173/`. Visiting the URL shows "GEO 诊断 Agent" placeholder.

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2" && git add frontend/ && git commit -m "feat(frontend): scaffold React + Vite + Tailwind project"
```

---

### Task 0.4: Docker Compose One-Command Startup

**Files:**
- Create: `D:/GEO2/backend/Dockerfile`
- Create: `D:/GEO2/frontend/Dockerfile`
- Create: `D:/GEO2/docker-compose.yml`
- Create: `D:/GEO2/backend/.dockerignore`
- Create: `D:/GEO2/frontend/.dockerignore`

- [ ] **Step 1: Create backend `Dockerfile`**

Create `D:/GEO2/backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# WeasyPrint 系统依赖（中文字体 + cairo + pango）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create frontend `Dockerfile`**

Create `D:/GEO2/frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

- [ ] **Step 3: Create `docker-compose.yml`**

Create `D:/GEO2/docker-compose.yml`:

```yaml
version: '3.9'

services:
  backend:
    build: ./backend
    container_name: geo-backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/data:/app/data
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 10s
      timeout: 5s
      retries: 3

  frontend:
    build: ./frontend
    container_name: geo-frontend
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/index.html:/app/index.html
    depends_on:
      backend:
        condition: service_healthy
```

- [ ] **Step 4: Create `.dockerignore` files**

Create `D:/GEO2/backend/.dockerignore`:

```
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.coverage
data/reports.db
data/reports/*.pdf
.env
.env.local
tests/
```

Create `D:/GEO2/frontend/.dockerignore`:

```
node_modules/
dist/
.vite/
*.log
.env
.env.local
```

- [ ] **Step 5: Verify docker-compose builds and runs**

```bash
cd "D:/GEO2" && cp .env.example .env && docker-compose up --build -d
```

Wait 30 seconds for services to be healthy, then verify:

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

Also visit http://localhost:5173 in browser - should show "GEO 诊断 Agent" placeholder.

Stop services:

```bash
cd "D:/GEO2" && docker-compose down
```

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add docker-compose.yml backend/Dockerfile backend/.dockerignore frontend/Dockerfile frontend/.dockerignore && git commit -m "feat: docker-compose for one-command backend + frontend startup"
```

---

## Phase 1: Data Layer

### Task 1.1: Database Setup + SQLAlchemy ORM (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/core/__init__.py`
- Create: `D:/GEO2/backend/app/core/config.py`
- Create: `D:/GEO2/backend/app/core/db.py`
- Create: `D:/GEO2/backend/app/models/__init__.py`
- Create: `D:/GEO2/backend/app/models/orm.py`
- Create: `D:/GEO2/backend/tests/test_db.py`
- Create: `D:/GEO2/backend/tests/conftest.py`

**Interfaces:**
- Consumes: `app.main:app`
- Produces:
  - `app.core.config.Settings` (Pydantic settings)
  - `app.core.db.engine` (async SQLAlchemy engine)
  - `app.core.db.async_session` (session factory)
  - `app.core.db.init_db()` (creates tables)
  - `app.models.orm.ReportORM` (SQLAlchemy model)

- [ ] **Step 1: Create `app/core/__init__.py`**

Create empty `D:/GEO2/backend/app/core/__init__.py`.

- [ ] **Step 2: Create `app/core/config.py`**

Create `D:/GEO2/backend/app/core/config.py`:

```python
"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings (env-driven)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Kimi
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"

    # LLM selection (comma-separated)
    llm_providers: str = "deepseek"

    # App
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    database_url: str = "sqlite+aiosqlite:///./data/reports.db"
    log_level: str = "INFO"

    # Timeouts
    diagnosis_total_timeout_s: int = 90
    llm_call_timeout_s: int = 30
    crawl_timeout_s: int = 10

    @property
    def enabled_providers(self) -> list[str]:
        """Parse llm_providers into list."""
        return [p.strip() for p in self.llm_providers.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
```

- [ ] **Step 3: Create `app/models/__init__.py`**

Create empty `D:/GEO2/backend/app/models/__init__.py`.

- [ ] **Step 4: Write failing test for DB setup**

Create `D:/GEO2/backend/tests/conftest.py`:

```python
"""Shared pytest fixtures."""
import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


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
```

Create `D:/GEO2/backend/tests/test_db.py`:

```python
"""Tests for database setup and ORM model."""
import pytest
from sqlalchemy import select

from app.models.orm import ReportORM


@pytest.mark.asyncio
async def test_create_and_read_report(db_session) -> None:
    """A row inserted via ORM can be read back."""
    report = ReportORM(
        id="test-id-1",
        task_id="task-id-1",
        brand_name="测试品牌",
        industry="电商",
        official_url="https://example.com",
        status="pending",
        request_json='{"brand_name":"测试品牌"}',
    )
    db_session.add(report)
    await db_session.commit()

    result = await db_session.execute(
        select(ReportORM).where(ReportORM.id == "test-id-1")
    )
    fetched = result.scalar_one()

    assert fetched.brand_name == "测试品牌"
    assert fetched.status == "pending"
    assert fetched.progress == 0  # default
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_default_progress_is_zero(db_session) -> None:
    """Newly inserted rows default progress to 0."""
    report = ReportORM(
        id="x",
        task_id="y",
        brand_name="b",
        industry="i",
        official_url="https://example.com",
        status="pending",
        request_json="{}",
    )
    db_session.add(report)
    await db_session.commit()
    assert report.progress == 0
```

- [ ] **Step 5: Create ORM model `app/models/orm.py`**

Create `D:/GEO2/backend/app/models/orm.py`:

```python
"""SQLAlchemy ORM models."""
from datetime import datetime, timezone

from sqlalchemy import Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """UTC now (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class ReportORM(Base):
    """Diagnostic report / task record.

    Stores both the task lifecycle (status, progress) and the full
    diagnosis request + completed report as JSON blobs.
    """

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    brand_name: Mapped[str] = mapped_column(String, nullable=False)
    industry: Mapped[str] = mapped_column(String, nullable=False)
    official_url: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    request_json: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
```

- [ ] **Step 6: Create `app/core/db.py`**

Create `D:/GEO2/backend/app/core/db.py`:

```python
"""Database engine and session management."""
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


async def dispose_db() -> None:
    """Clean shutdown — release connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
```

- [ ] **Step 7: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_db.py -v
```

Expected: Both tests PASS.

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): database setup with SQLAlchemy async ORM + tests"
```

---

### Task 1.2: Pydantic API Models

**Files:**
- Create: `D:/GEO2/backend/app/models/schemas.py`
- Create: `D:/GEO2/backend/tests/test_schemas.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `DiagnosisRequest`, `DiagnosisTask`, `TaskStatus`
  - `MentionResult`, `SchemaCoverage`, `EeatSignals`, `StructureScore`, `FreshnessScore`, `SiteAudit`
  - `DimensionScore`, `ScoreCard`, `Suggestion`, `Report`, `BrandInfo`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_schemas.py`:

```python
"""Tests for Pydantic schema validation."""
import pytest
from pydantic import ValidationError

from app.models.schemas import (
    DiagnosisRequest,
    DimensionScore,
    TaskStatus,
)


class TestDiagnosisRequest:
    def test_valid_request_passes(self) -> None:
        req = DiagnosisRequest(
            brand_name="小米",
            industry="手机",
            official_url="https://www.mi.com",
            target_questions=["小米手机怎么样", "小米14值得买吗", "小米vs华为"],
        )
        assert req.brand_name == "小米"
        assert len(req.target_questions) == 3
        assert req.competitors == []  # default

    def test_url_must_be_valid(self) -> None:
        with pytest.raises(ValidationError):
            DiagnosisRequest(
                brand_name="x",
                industry="y",
                official_url="not-a-url",
                target_questions=["q1", "q2", "q3"],
            )

    def test_min_three_questions(self) -> None:
        with pytest.raises(ValidationError):
            DiagnosisRequest(
                brand_name="x",
                industry="y",
                official_url="https://example.com",
                target_questions=["only one"],
            )


class TestDimensionScore:
    def test_score_bounds(self) -> None:
        DimensionScore(name="权威度", score=8.5, weight=0.25, evidence=["x"])
        with pytest.raises(ValidationError):
            DimensionScore(name="x", score=11.0, weight=0.25, evidence=[])


class TestTaskStatus:
    def test_enum_values(self) -> None:
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.schemas'`

- [ ] **Step 3: Create `app/models/schemas.py`**

Create `D:/GEO2/backend/app/models/schemas.py`:

```python
"""Pydantic models for API + domain layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class TaskStatus(str, Enum):
    """Lifecycle states of a diagnosis task."""

    PENDING = "pending"
    CRAWLING = "crawling"
    QUERYING_LLM = "querying_llm"
    SCORING = "scoring"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Request ---


class DiagnosisRequest(BaseModel):
    """User-submitted diagnosis request."""

    brand_name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    official_url: HttpUrl
    target_questions: list[str] = Field(..., min_length=3, max_length=5)
    competitors: list[str] = Field(default_factory=list, max_length=10)
    contact_email: EmailStr | None = None


# --- Task lifecycle ---


class DiagnosisTask(BaseModel):
    """Task state exposed via status polling API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    request: DiagnosisRequest
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Mention / LLM result ---


class MentionResult(BaseModel):
    """Result of asking one question to one LLM."""

    question: str
    llm_provider: str
    llm_answer: str
    brand_mentioned: bool
    mention_position: int | None = None
    competitors_mentioned: list[str] = Field(default_factory=list)
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    error: str | None = None  # set when this sample should be excluded from rates


# --- Site audit sub-models ---


class SchemaCoverage(BaseModel):
    has_organization: bool = False
    has_website: bool = False
    has_faq: bool = False
    has_article: bool = False
    has_breadcrumb: bool = False
    has_product: bool = False
    detected_schemas: list[str] = Field(default_factory=list)


class EeatSignals(BaseModel):
    has_author_bio: bool = False
    has_contact_page: bool = False
    has_about_page: bool = False
    third_party_mentions: int = 0
    has_expert_attribution: bool = False


class StructureScore(BaseModel):
    h1_count_ok: bool = False
    heading_hierarchy_valid: bool = False
    has_lists_or_tables: bool = False
    avg_paragraph_length: int = 0
    bluf_score: float = 0.0


class FreshnessScore(BaseModel):
    last_modified: datetime | None = None
    days_since_update: int | None = None
    has_publish_date: bool = False
    has_recent_mention_in_content: bool = False


class SiteAudit(BaseModel):
    url: str
    crawl_status: Literal["success", "partial", "failed"] = "success"
    crawled_at: datetime
    schema: SchemaCoverage = Field(default_factory=SchemaCoverage)
    eeat: EeatSignals = Field(default_factory=EeatSignals)
    structure: StructureScore = Field(default_factory=StructureScore)
    freshness: FreshnessScore = Field(default_factory=FreshnessScore)
    page_load_ms: int | None = None
    robots_txt_allows_ai_bots: dict[str, bool] = Field(default_factory=dict)


# --- Scoring ---


class DimensionScore(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=10)
    weight: float = Field(..., ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ScoreCard(BaseModel):
    authority: DimensionScore
    relevance: DimensionScore
    structure: DimensionScore
    freshness: DimensionScore
    verifiability: DimensionScore
    overall: float = Field(..., ge=0, le=100)
    mention_rate: float = Field(..., ge=0, le=1)
    avg_mention_position: float | None = None


class Suggestion(BaseModel):
    priority: Literal["P0", "P1", "P2"]
    category: str
    title: str
    detail: str
    action_steps: list[str] = Field(default_factory=list)
    expected_impact: str


# --- Brand info / final report ---


class BrandInfo(BaseModel):
    name: str
    industry: str
    official_url: str


class Report(BaseModel):
    id: str
    task_id: str
    brand: BrandInfo
    site_audit: SiteAudit | None = None
    mentions: list[MentionResult] = Field(default_factory=list)
    score_card: ScoreCard
    suggestions: list[Suggestion] = Field(default_factory=list)
    summary: str
    created_at: datetime
    pdf_available: bool = False
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_schemas.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): Pydantic schemas for API and domain layer"
```

---

### Task 1.3: Report Repository Layer

**Files:**
- Create: `D:/GEO2/backend/app/repositories/__init__.py`
- Create: `D:/GEO2/backend/app/repositories/report_repo.py`
- Create: `D:/GEO2/backend/tests/test_report_repo.py`

**Interfaces:**
- Consumes: `app.models.orm.ReportORM`, `app.core.db.get_session_factory`
- Produces:
  - `ReportRepository.create(req) -> ReportORM`
  - `ReportRepository.get_by_id(id) -> ReportORM | None`
  - `ReportRepository.get_by_task_id(task_id) -> ReportORM | None`
  - `ReportRepository.update_status(task_id, status, progress, error=None) -> None`
  - `ReportRepository.update_report(task_id, report_json, pdf_path=None) -> None`
  - `ReportRepository.list_recent(limit=50) -> list[ReportORM]`

- [ ] **Step 1: Create `app/repositories/__init__.py`**

Create empty `D:/GEO2/backend/app/repositories/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_report_repo.py`:

```python
"""Tests for the ReportRepository."""
import pytest

from app.models.orm import ReportORM
from app.models.schemas import DiagnosisRequest
from app.repositories.report_repo import ReportRepository


@pytest.mark.asyncio
async def test_create_returns_orm_with_id(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="测试",
        industry="电商",
        official_url="https://example.com",
        target_questions=["q1", "q2", "q3"],
    )
    row = await repo.create(req)

    assert row.id != ""
    assert row.task_id == row.id
    assert row.status == "pending"
    assert row.progress == 0
    assert '"brand_name": "测试"' in row.request_json


@pytest.mark.asyncio
async def test_get_by_id_returns_created(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    created = await repo.create(req)
    fetched = await repo.get_by_id(created.id)

    assert fetched is not None
    assert fetched.brand_name == "X"


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing(db_session) -> None:
    repo = ReportRepository(db_session)
    fetched = await repo.get_by_id("nonexistent")
    assert fetched is None


@pytest.mark.asyncio
async def test_update_status_changes_fields(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    row = await repo.create(req)

    await repo.update_status(row.task_id, status="crawling", progress=20)
    refreshed = await repo.get_by_task_id(row.task_id)
    assert refreshed.status == "crawling"
    assert refreshed.progress == 20


@pytest.mark.asyncio
async def test_update_report_writes_json_and_pdf(db_session) -> None:
    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    row = await repo.create(req)

    await repo.update_report(
        row.task_id,
        report_json='{"score_card":{"overall":80}}',
        pdf_path="/tmp/report.pdf",
    )
    refreshed = await repo.get_by_task_id(row.task_id)
    assert refreshed.report_json is not None
    assert refreshed.pdf_path == "/tmp/report.pdf"


@pytest.mark.asyncio
async def test_list_recent_orders_by_created_desc(db_session) -> None:
    repo = ReportRepository(db_session)
    ids = []
    for i in range(3):
        req = DiagnosisRequest(
            brand_name=f"B{i}", industry="X", official_url="https://example.com",
            target_questions=["a", "b", "c"],
        )
        row = await repo.create(req)
        ids.append(row.id)

    recent = await repo.list_recent(limit=10)
    assert len(recent) == 3
    # most recently created should be first
    assert recent[0].id == ids[-1]
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_report_repo.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.repositories'`

- [ ] **Step 4: Create `app/repositories/report_repo.py`**

Create `D:/GEO2/backend/app/repositories/report_repo.py`:

```python
"""Repository for ReportORM — all DB access for the reports table."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ReportORM
from app.models.schemas import DiagnosisRequest


class ReportRepository:
    """Data access for the reports table.

    All methods are async and require a session bound to a transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, req: DiagnosisRequest) -> ReportORM:
        """Insert a new pending task. Returns the persisted row."""
        new_id = str(uuid.uuid4())
        row = ReportORM(
            id=new_id,
            task_id=new_id,
            brand_name=req.brand_name,
            industry=req.industry,
            official_url=str(req.official_url),
            status="pending",
            progress=0,
            request_json=req.model_dump_json(),
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_id(self, id: str) -> ReportORM | None:
        """Fetch by primary key."""
        result = await self.session.execute(
            select(ReportORM).where(ReportORM.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_task_id(self, task_id: str) -> ReportORM | None:
        """Fetch by task_id (== id in MVP)."""
        return await self.get_by_id(task_id)

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: int,
        error: str | None = None,
    ) -> None:
        """Update lifecycle status and progress."""
        row = await self.get_by_task_id(task_id)
        if row is None:
            return
        row.status = status
        row.progress = progress
        if error is not None:
            row.error_message = error
        row.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_report(
        self,
        task_id: str,
        report_json: str,
        pdf_path: str | None = None,
    ) -> None:
        """Write the final report JSON and optional PDF path."""
        row = await self.get_by_task_id(task_id)
        if row is None:
            return
        row.report_json = report_json
        if pdf_path is not None:
            row.pdf_path = pdf_path
        row.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def list_recent(self, limit: int = 50) -> list[ReportORM]:
        """List reports ordered by creation time descending."""
        result = await self.session.execute(
            select(ReportORM).order_by(ReportORM.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_report_repo.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): ReportRepository with CRUD + tests"
```

---

## Phase 2: Domain Exceptions + LLM Client

### Task 2.1: Domain Exception Classes

**Files:**
- Create: `D:/GEO2/backend/app/domain/__init__.py`
- Create: `D:/GEO2/backend/app/domain/exceptions.py`
- Create: `D:/GEO2/backend/tests/test_exceptions.py`

**Interfaces:**
- Consumes: nothing
- Produces: `DomainError`, `CrawlError`, `LlmError`, `ScoreError`, `RenderError`

- [ ] **Step 1: Create `app/domain/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_exceptions.py`:

```python
"""Tests for domain exception hierarchy."""
import pytest

from app.domain.exceptions import CrawlError, DomainError, LlmError, RenderError


class TestHierarchy:
    def test_all_inherit_from_domain_error(self) -> None:
        assert issubclass(CrawlError, DomainError)
        assert issubclass(LlmError, DomainError)
        assert issubclass(RenderError, DomainError)


class TestCrawlError:
    def test_carries_url_and_reason(self) -> None:
        err = CrawlError(reason="DNS lookup failed", url="https://x.example")
        assert err.reason == "DNS lookup failed"
        assert err.url == "https://x.example"
        assert "DNS lookup failed" in str(err)


class TestLlmError:
    def test_retryable_flag(self) -> None:
        retryable = LlmError(provider="deepseek", message="rate limit", retryable=True)
        permanent = LlmError(provider="deepseek", message="bad key", retryable=False)
        assert retryable.retryable is True
        assert permanent.retryable is False
        with pytest.raises(LlmError):
            raise retryable
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_exceptions.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain'`

- [ ] **Step 4: Create `app/domain/exceptions.py`**

Create `D:/GEO2/backend/app/domain/exceptions.py`:

```python
"""Custom exceptions for the domain layer."""


class DomainError(Exception):
    """Base for all domain-level errors."""


class CrawlError(DomainError):
    """Website could not be crawled to a usable state."""

    def __init__(self, reason: str, url: str) -> None:
        self.reason = reason
        self.url = url
        super().__init__(f"Crawl failed for {url}: {reason}")


class LlmError(DomainError):
    """LLM call failed."""

    def __init__(self, provider: str, message: str, retryable: bool) -> None:
        self.provider = provider
        self.retryable = retryable
        super().__init__(f"LLM error ({provider}): {message}")


class ScoreError(DomainError):
    """Scoring engine encountered invalid data."""


class RenderError(DomainError):
    """PDF/HTML rendering failed."""
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_exceptions.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): domain exception hierarchy"
```

---

### Task 2.2: LLM Client — DeepSeek Provider (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/domain/llm_client.py`
- Create: `D:/GEO2/backend/tests/test_llm_client.py`
- Modify: `D:/GEO2/backend/app/core/config.py:1-10` (allow `.env` in dev)

**Interfaces:**
- Consumes: `app.core.config.Settings`, `openai.AsyncOpenAI`
- Produces:
  - `LLMClient.query_mentions(brand, industry, questions, providers=None) -> list[MentionResult]`
  - `LLMClient.query_single(provider, question, brand, industry) -> MentionResult`

- [ ] **Step 1: Write failing test (mocked HTTP)**

Create `D:/GEO2/backend/tests/test_llm_client.py`:

```python
"""Tests for LLM client. Uses respx to mock httpx calls."""
from __future__ import annotations

from unittest.mock import patch

import pytest
import respx
from httpx import Response

from app.core.config import Settings
from app.domain.llm_client import LLMClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=10,
    )


@pytest.fixture
def client(settings: Settings) -> LLMClient:
    return LLMClient(settings)


@pytest.mark.asyncio
@respx.mock
async def test_query_single_finds_mention(client: LLMClient) -> None:
    """When LLM mentions brand, brand_mentioned is True."""
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "在国产手机中，小米是不错的选择，品质可靠。"
                        }
                    }
                ]
            },
        )
    )

    result = await client.query_single(
        provider="deepseek",
        question="国产手机推荐",
        brand="小米",
        industry="手机",
    )

    assert result.brand_mentioned is True
    assert result.mention_position is not None
    assert result.llm_provider == "deepseek"


@pytest.mark.asyncio
@respx.mock
async def test_query_single_no_mention(client: LLMClient) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={"choices": [{"message": {"content": "苹果和华为是常见选择。"}}]},
        )
    )

    result = await client.query_single(
        provider="deepseek", question="手机推荐", brand="小米", industry="手机",
    )

    assert result.brand_mentioned is False
    assert result.mention_position is None


@pytest.mark.asyncio
@respx.mock
async def test_query_single_handles_timeout(client: LLMClient) -> None:
    import httpx

    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=httpx.TimeoutException("timeout")
    )

    result = await client.query_single(
        provider="deepseek", question="q", brand="b", industry="i",
    )

    assert result.brand_mentioned is False
    assert result.error is not None


@pytest.mark.asyncio
@respx.mock
async def test_query_mentions_runs_in_parallel(client: LLMClient) -> None:
    """Multiple questions should be queried concurrently."""
    import time

    call_count = 0

    async def slow_handler(request):
        nonlocal call_count
        call_count += 1
        return Response(200, json={"choices": [{"message": {"content": "小米不错"}}]})

    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=slow_handler
    )

    start = time.monotonic()
    results = await client.query_mentions(
        brand="小米",
        industry="手机",
        questions=["q1", "q2", "q3"],
        providers=["deepseek"],
    )
    elapsed = time.monotonic() - start

    assert len(results) == 3
    # 3 calls but parallel — should be much faster than 3x sequential
    assert call_count == 3
    assert elapsed < 5  # generous bound
```

Add `respx` to requirements:

- [ ] **Step 2: Add `respx` to requirements**

Edit `D:/GEO2/backend/requirements.txt` and add at the bottom:

```
respx==0.21.1
```

Then:

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pip install respx==0.21.1
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_llm_client.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.llm_client'`

- [ ] **Step 4: Create `app/domain/llm_client.py`**

Create `D:/GEO2/backend/app/domain/llm_client.py`:

```python
"""LLM client — DeepSeek + Kimi via OpenAI-compatible API.

Each provider is selected at runtime via Settings.enabled_providers.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import Settings
from app.domain.exceptions import LlmError
from app.models.schemas import MentionResult

logger = structlog.get_logger()


class _ProviderConfig(BaseModel):
    """Per-provider config resolved from Settings."""

    api_key: str
    base_url: str
    model: str


def _build_provider_map(settings: Settings) -> dict[str, _ProviderConfig]:
    return {
        "deepseek": _ProviderConfig(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        ),
        "kimi": _ProviderConfig(
            api_key=settings.kimi_api_key,
            base_url=settings.kimi_base_url,
            model=settings.kimi_model,
        ),
    }


class LLMClient:
    """Async client supporting multiple OpenAI-compatible providers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers = _build_provider_map(settings)

    def _make_async_client(self, cfg: _ProviderConfig) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=self.settings.llm_call_timeout_s,
        )

    async def query_single(
        self,
        provider: str,
        question: str,
        brand: str,
        industry: str,
        max_retries: int = 1,
    ) -> MentionResult:
        """Query one provider with one question. Returns MentionResult.

        On failure, retries up to max_retries times. Returns a
        MentionResult with `error` set rather than raising.
        """
        cfg = self._providers.get(provider)
        if cfg is None:
            return MentionResult(
                question=question,
                llm_provider=provider,
                llm_answer="",
                brand_mentioned=False,
                error=f"unknown provider: {provider}",
            )

        prompt = self._build_prompt(question, brand, industry)
        last_error: str | None = None

        for attempt in range(max_retries + 1):
            try:
                client = self._make_async_client(cfg)
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=cfg.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                    ),
                    timeout=self.settings.llm_call_timeout_s,
                )
                answer = response.choices[0].message.content or ""
                return self._parse_answer(question, provider, brand, answer)

            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning("llm_timeout", provider=provider, attempt=attempt)
            except LlmError as e:
                last_error = str(e)
                if not e.retryable:
                    break
                logger.warning("llm_error", provider=provider, attempt=attempt, error=e)
            except (httpx.HTTPError, Exception) as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    "llm_unexpected", provider=provider, attempt=attempt, error=last_error
                )

        return MentionResult(
            question=question,
            llm_provider=provider,
            llm_answer="",
            brand_mentioned=False,
            sentiment="neutral",
            error=last_error,
        )

    async def query_mentions(
        self,
        brand: str,
        industry: str,
        questions: list[str],
        providers: list[str] | None = None,
    ) -> list[MentionResult]:
        """Query all (provider × question) pairs in parallel."""
        active = providers or self.settings.enabled_providers
        tasks: list[asyncio.Task[MentionResult]] = []
        for provider in active:
            for question in questions:
                tasks.append(
                    asyncio.create_task(
                        self.query_single(provider, question, brand, industry)
                    )
                )
        return await asyncio.gather(*tasks)

    @staticmethod
    def _build_prompt(question: str, brand: str, industry: str) -> str:
        return (
            f"请像回答用户提问一样回答：\"{question}\"\n"
            f"如果答案涉及 {industry} 行业的产品/品牌/服务，"
            f"请在合适位置提到\"{brand}\"品牌（如果相关）。\n"
            f"只输出答案文本，不要额外说明。"
        )

    @staticmethod
    def _parse_answer(
        question: str, provider: str, brand: str, answer: str
    ) -> MentionResult:
        """Detect brand mention and its position in the answer."""
        mentioned, position = _detect_mention(answer, brand)
        return MentionResult(
            question=question,
            llm_provider=provider,
            llm_answer=answer,
            brand_mentioned=mentioned,
            mention_position=position,
            sentiment="neutral",  # sentiment handled in a later task
        )


def _detect_mention(text: str, brand: str) -> tuple[bool, int | None]:
    """Return (mentioned, 1-based position) for the brand in text."""
    if not brand:
        return False, None
    # Naive substring match; brand names containing regex metachars are
    # escaped. Sentence-based position counter.
    sentences = re.split(r"[。！？\n]+", text)
    for idx, sentence in enumerate(sentences, start=1):
        if not sentence.strip():
            continue
        if re.search(re.escape(brand), sentence):
            return True, idx
    return False, None
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_llm_client.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): LLM client with DeepSeek provider + parallel queries + tests"
```

---

### Task 2.3: LLM Client — Add Kimi via Settings (No Code Change)

**Files:**
- Modify: `D:/GEO2/backend/.env.example:11-13` (already includes Kimi)
- No new tests; covered by Task 2.2 (provider dispatch is parameterized)

**Rationale:** The `LLMClient` already supports Kimi via the `_build_provider_map` function. Kimi activation is purely a configuration concern (set `KIMI_API_KEY` and add `kimi` to `LLM_PROVIDERS`). No code changes required.

- [ ] **Step 1: Document Kimi activation in README**

Add to `D:/GEO2/README.md` (in 开发 or 快速开始 section):

```markdown
### 启用 Kimi 作为第二个 LLM

编辑 `.env`：

\`\`\`bash
KIMI_API_KEY=sk-your-kimi-key
LLM_PROVIDERS=deepseek,kimi
\`\`\`

重启后端容器：

\`\`\`bash
docker-compose restart backend
\`\`\`

诊断时会同时调用 DeepSeek 和 Kimi，每个问题产生 2 条 MentionResult。
```

- [ ] **Step 2: Manual verification**

With `.env` containing both providers, run the existing tests:

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_llm_client.py -v
```

Expected: All pass (tests use mocked httpx so real keys aren't required).

- [ ] **Step 3: Commit**

```bash
cd "D:/GEO2" && git add README.md && git commit -m "docs: document how to enable Kimi as second LLM provider"
```

---

## Phase 3: Web Crawler

### Task 3.1: Crawler Foundation — Homepage Fetch (TDD)

**Files:**
- Create: `D:/GEO2/backend/app/domain/crawler.py`
- Create: `D:/GEO2/backend/tests/test_crawler.py`

**Interfaces:**
- Consumes: `app.core.config.Settings`
- Produces:
  - `CrawlerResult` (Pydantic model — internal use)
  - `Crawler.fetch(url) -> CrawlerResult`
  - `Crawler.fetch_robots_txt(base_url) -> str | None`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_crawler.py`:

```python
"""Tests for the web crawler. Uses respx to mock HTTP calls."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from app.core.config import Settings
from app.domain.crawler import Crawler


@pytest.fixture
def settings() -> Settings:
    return Settings(crawl_timeout_s=5)


@pytest.fixture
def crawler(settings: Settings) -> Crawler:
    return Crawler(settings)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_html_on_success(crawler: Crawler) -> None:
    respx.get("https://example.com").mock(
        return_value=Response(
            200,
            text="<html><head><title>Test</title></head><body><h1>Hello</h1></body></html>",
            headers={"content-type": "text/html"},
        )
    )

    result = await crawler.fetch("https://example.com")

    assert result.success is True
    assert result.status_code == 200
    assert "<h1>Hello</h1>" in result.html
    assert result.url == "https://example.com"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_returns_failure_on_timeout(crawler: Crawler) -> None:
    import httpx

    respx.get("https://slow.example.com").mock(side_effect=httpx.TimeoutException())

    result = await crawler.fetch("https://slow.example.com")

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_robots_txt_returns_text_when_exists(crawler: Crawler) -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=Response(
            200, text="User-agent: *\nAllow: /\n"
        )
    )

    text = await crawler.fetch_robots_txt("https://example.com")

    assert text is not None
    assert "User-agent" in text


@pytest.mark.asyncio
@respx.mock
async def test_fetch_robots_txt_returns_none_on_404(crawler: Crawler) -> None:
    respx.get("https://example.com/robots.txt").mock(return_value=Response(404))

    text = await crawler.fetch_robots_txt("https://example.com")

    assert text is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.crawler'`

- [ ] **Step 3: Create `app/domain/crawler.py`**

Create `D:/GEO2/backend/app/domain/crawler.py`:

```python
"""Async web crawler for homepage + robots.txt + sitemap."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
import structlog

from app.core.config import Settings

logger = structlog.get_logger()


@dataclass
class CrawlerResult:
    """Result of fetching a single URL."""

    url: str
    success: bool
    status_code: int | None
    html: str
    elapsed_ms: int | None
    error: str | None = None


class Crawler:
    """Async HTTP fetcher with timeout + UA."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (compatible; GEO-Agent/0.1; +https://example.com/bot)"
    )

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.settings.crawl_timeout_s,
                follow_redirects=True,
                headers={"User-Agent": self.DEFAULT_USER_AGENT},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, url: str) -> CrawlerResult:
        """Fetch a URL, returning success/failure + html or error."""
        client = self._get_client()
        try:
            response = await client.get(url)
            elapsed_ms = int(response.elapsed.total_seconds() * 1000)
            if response.status_code >= 400:
                return CrawlerResult(
                    url=url,
                    success=False,
                    status_code=response.status_code,
                    html="",
                    elapsed_ms=elapsed_ms,
                    error=f"HTTP {response.status_code}",
                )
            return CrawlerResult(
                url=url,
                success=True,
                status_code=response.status_code,
                html=response.text,
                elapsed_ms=elapsed_ms,
            )
        except httpx.TimeoutException:
            return CrawlerResult(
                url=url, success=False, status_code=None,
                html="", elapsed_ms=None, error="timeout",
            )
        except httpx.HTTPError as e:
            return CrawlerResult(
                url=url, success=False, status_code=None,
                html="", elapsed_ms=None, error=f"{type(e).__name__}: {e}",
            )

    async def fetch_robots_txt(self, base_url: str) -> str | None:
        """Fetch /robots.txt. Returns text or None on 404/error."""
        parsed = urlparse(base_url)
        robots_url = urljoin(base_url, "/robots.txt")
        result = await self.fetch(robots_url)
        if not result.success:
            return None
        return result.html
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): async web crawler foundation + tests"
```

---

### Task 3.2: Crawler — Schema, EEAT, Structure Extraction (TDD)

**Files:**
- Modify: `D:/GEO2/backend/app/domain/crawler.py` (add extraction methods)
- Modify: `D:/GEO2/backend/tests/test_crawler.py` (add extraction tests)

**Interfaces (additions):**
- `Crawler.extract_schema_coverage(html: str) -> SchemaCoverage`
- `Crawler.extract_eeat_signals(html: str, base_url: str) -> EeatSignals`
- `Crawler.extract_structure(html: str) -> StructureScore`
- `Crawler.extract_freshness(html: str, headers: dict | None) -> FreshnessScore`

- [ ] **Step 1: Append failing tests to `test_crawler.py`**

Append to `D:/GEO2/backend/tests/test_crawler.py`:

```python
class TestSchemaExtraction:
    def test_extracts_organization_schema(self) -> None:
        from app.domain.crawler import Crawler
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Organization", "name": "Acme"}
        </script>
        </head><body></body></html>
        '''
        result = Crawler.extract_schema_coverage(html)
        assert result.has_organization is True
        assert "Organization" in result.detected_schemas

    def test_no_schemas_detected(self) -> None:
        from app.domain.crawler import Crawler
        html = "<html><body>plain</body></html>"
        result = Crawler.extract_schema_coverage(html)
        assert result.has_organization is False
        assert result.detected_schemas == []


class TestStructureExtraction:
    def test_single_h1_is_valid(self) -> None:
        from app.domain.crawler import Crawler
        html = "<h1>Title</h1><h2>S1</h2><h3>Sub</h3><p>Text.</p>"
        score = Crawler.extract_structure(html)
        assert score.h1_count_ok is True
        assert score.heading_hierarchy_valid is True

    def test_multiple_h1_invalid(self) -> None:
        from app.domain.crawler import Crawler
        html = "<h1>A</h1><h1>B</h1>"
        score = Crawler.extract_structure(html)
        assert score.h1_count_ok is False


class TestEeatExtraction:
    def test_detects_contact_and_about_links(self) -> None:
        from app.domain.crawler import Crawler
        html = '<a href="/about">About</a><a href="/contact">Contact</a>'
        result = Crawler.extract_eeat_signals(html, "https://example.com")
        assert result.has_about_page is True
        assert result.has_contact_page is True
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py::TestSchemaExtraction tests/test_crawler.py::TestStructureExtraction tests/test_crawler.py::TestEeatExtraction -v
```

Expected: FAIL with `AttributeError: type object 'Crawler' has no attribute 'extract_schema_coverage'`

- [ ] **Step 3: Add extraction methods to `crawler.py`**

Add these methods to the `Crawler` class in `D:/GEO2/backend/app/domain/crawler.py`:

```python
    # ---- Extraction methods (pure functions of html) ----

    @staticmethod
    def extract_schema_coverage(html: str) -> "SchemaCoverage":
        """Detect JSON-LD schema types in the page."""
        from app.models.schemas import SchemaCoverage

        detected: list[str] = []
        # Find all JSON-LD script blocks
        pattern = re.compile(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        for match in pattern.finditer(html):
            try:
                data = json.loads(match.group(1))
                types = _extract_schema_types(data)
                detected.extend(types)
            except (json.JSONDecodeError, ValueError):
                continue

        detected = list(dict.fromkeys(detected))  # dedupe, preserve order
        return SchemaCoverage(
            has_organization="Organization" in detected,
            has_website="WebSite" in detected,
            has_faq="FAQPage" in detected,
            has_article="Article" in detected or "NewsArticle" in detected,
            has_breadcrumb="BreadcrumbList" in detected,
            has_product="Product" in detected,
            detected_schemas=detected,
        )

    @staticmethod
    def extract_eeat_signals(html: str, base_url: str) -> "EeatSignals":
        """Detect author bio, contact page, about page, etc."""
        from app.models.schemas import EeatSignals

        lowered = html.lower()
        has_author_bio = bool(re.search(r'class=["\'][^"\']*author[^"\']*["\']', lowered))
        has_contact = bool(re.search(r'href=["\'][^"\']*contact', lowered))
        has_about = bool(re.search(r'href=["\'][^"\']*(about|关于)', lowered))
        return EeatSignals(
            has_author_bio=has_author_bio,
            has_contact_page=has_contact,
            has_about_page=has_about,
            third_party_mentions=0,  # computed later via backlink analysis
            has_expert_attribution=has_author_bio,
        )

    @staticmethod
    def extract_structure(html: str) -> "StructureScore":
        """Score heading hierarchy + paragraph length."""
        from app.models.schemas import StructureScore

        h1_matches = re.findall(r"<h1[^>]*>", html, re.IGNORECASE)
        h2_matches = re.findall(r"<h2[^>]*>", html, re.IGNORECASE)
        h3_matches = re.findall(r"<h3[^>]*>", html, re.IGNORECASE)

        h1_ok = len(h1_matches) == 1
        # Hierarchy: at least one H2 if H3s exist
        hierarchy_valid = len(h3_matches) == 0 or len(h2_matches) >= 1

        has_lists = bool(re.search(r"<(ul|ol|table)[^>]*>", html, re.IGNORECASE))

        # Avg paragraph length (Chinese-aware via chars)
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
        if paragraphs:
            # Strip tags from paragraph content
            stripped = [re.sub(r"<[^>]+>", "", p) for p in paragraphs]
            avg_len = sum(len(p) for p in stripped) // max(len(stripped), 1)
        else:
            avg_len = 0

        # BLUF heuristic: first 30% of body has a "summary" sentence
        # For MVP, simple proxy: presence of a TL;DR / 简介 / 概述 keyword
        body_text = re.sub(r"<[^>]+>", "", html)[:1000]
        bluf_keywords = ["总结", "概述", "简介", "TL;DR", "Conclusion", "Summary"]
        bluf = 1.0 if any(kw in body_text for kw in bluf_keywords) else 0.5

        return StructureScore(
            h1_count_ok=h1_ok,
            heading_hierarchy_valid=hierarchy_valid,
            has_lists_or_tables=has_lists,
            avg_paragraph_length=avg_len,
            bluf_score=bluf,
        )

    @staticmethod
    def extract_freshness(
        html: str, last_modified_header: str | None
    ) -> "FreshnessScore":
        """Score content freshness from headers + meta tags."""
        from datetime import datetime, timezone, timedelta

        from app.models.schemas import FreshnessScore

        last_modified = _parse_http_date(last_modified_header)

        # Try to find datePublished in JSON-LD
        match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"', html, re.IGNORECASE
        )
        if match and last_modified is None:
            last_modified = _parse_iso8601(match.group(1))

        days_since = None
        if last_modified is not None:
            now = datetime.now(timezone.utc)
            days_since = max((now - last_modified).days, 0)

        has_publish_date = last_modified is not None
        recent_mention = bool(
            re.search(r"2024|2025|2026", html)
        )

        return FreshnessScore(
            last_modified=last_modified,
            days_since_update=days_since,
            has_publish_date=has_publish_date,
            has_recent_mention_in_content=recent_mention,
        )
```

Also add the import at the top of `crawler.py`:

```python
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
```

Add helpers at the bottom of `crawler.py`:

```python
def _extract_schema_types(data: object) -> list[str]:
    """Recursively collect @type values from a JSON-LD object/array."""
    types: list[str] = []
    if isinstance(data, dict):
        t = data.get("@type")
        if isinstance(t, str):
            types.append(t)
        elif isinstance(t, list):
            types.extend(t for t in t if isinstance(t, str))
        for v in data.values():
            if isinstance(v, (dict, list)):
                types.extend(_extract_schema_types(v))
    elif isinstance(data, list):
        for item in data:
            types.extend(_extract_schema_types(item))
    return types


def _parse_http_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _parse_iso8601(value: str) -> datetime | None:
    try:
        # Handle Z suffix
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): crawler schema/eeat/structure/freshness extraction + tests"
```

---

### Task 3.3: Crawler — robots.txt AI Bot Whitelist

**Files:**
- Modify: `D:/GEO2/backend/app/domain/crawler.py` (add method)
- Modify: `D:/GEO2/backend/tests/test_crawler.py` (add tests)

**Interfaces (additions):**
- `Crawler.check_ai_bot_whitelist(robots_txt: str | None) -> dict[str, bool]`

The method returns a dict keyed by AI bot name, value = whether the bot is allowed.

- [ ] **Step 1: Append failing test**

Append to `D:/GEO2/backend/tests/test_crawler.py`:

```python
class TestAiBotWhitelist:
    def test_open_bots_allowed_when_no_robots_txt(self) -> None:
        from app.domain.crawler import Crawler
        result = Crawler.check_ai_bot_whitelist(None)
        # By default (no robots.txt), all bots allowed
        assert result["GPTBot"] is True
        assert result["ClaudeBot"] is True

    def test_specific_bot_disallow(self) -> None:
        from app.domain.crawler import Crawler
        robots = """
User-agent: GPTBot
Disallow: /

User-agent: *
Allow: /
"""
        result = Crawler.check_ai_bot_whitelist(robots)
        assert result["GPTBot"] is False
        # * applies to unspecified bots including ClaudeBot
        assert result["ClaudeBot"] is True

    def test_explicit_allow(self) -> None:
        from app.domain.crawler import Crawler
        robots = """
User-agent: ClaudeBot
Allow: /
"""
        result = Crawler.check_ai_bot_whitelist(robots)
        assert result["ClaudeBot"] is True
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py::TestAiBotWhitelist -v
```

Expected: FAIL with `AttributeError`

- [ ] **Step 3: Add method to `crawler.py`**

Add to the `Crawler` class in `D:/GEO2/backend/app/domain/crawler.py`:

```python
    AI_BOTS = (
        "GPTBot",
        "ClaudeBot",
        "anthropic-ai",
        "Bytespider",
        "CCBot",
        "Google-Extended",
        "PerplexityBot",
    )

    @classmethod
    def check_ai_bot_whitelist(cls, robots_txt: str | None) -> dict[str, bool]:
        """For each known AI bot, determine if robots.txt allows it.

        If robots_txt is None (file missing), all bots are considered allowed.
        Otherwise, parse simple User-agent / Allow / Disallow rules.
        """
        if robots_txt is None:
            return {bot: True for bot in cls.AI_BOTS}

        rules = _parse_robots(robots_txt)
        result: dict[str, bool] = {}
        for bot in cls.AI_BOTS:
            result[bot] = _bot_is_allowed(bot, rules)
        return result
```

Add helpers at the bottom of `crawler.py`:

```python
def _parse_robots(text: str) -> list[tuple[str | None, list[tuple[str, str]]]]:
    """Parse robots.txt into list of (user_agent, [(directive, value)]).

    Returns a list preserving order; consecutive User-agent lines for the
    same agent are merged.
    """
    rules: list[tuple[str | None, list[tuple[str, str]]]] = []
    current_agents: list[str] = []
    current_directives: list[tuple[str, str]] = []

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if current_agents and current_directives:
                for agent in current_agents:
                    rules.append((agent.lower(), list(current_directives)))
                current_directives = []
            current_agents.append(value)
        elif key in ("allow", "disallow"):
            current_directives.append((key, value))
        # ignore other directives (sitemap, crawl-delay, etc.)

    if current_agents and current_directives:
        for agent in current_agents:
            rules.append((agent.lower(), list(current_directives)))

    return rules


def _bot_is_allowed(bot: str, rules: list[tuple[str | None, list[tuple[str, str]]]]) -> bool:
    """Determine if a specific bot is allowed.

    Rule selection: prefer rules where user-agent == bot; fall back to '*'.
    Within selected rules, longest matching path wins; Allow beats Disallow
    on ties.
    """
    bot_lower = bot.lower()
    candidates: list[tuple[str, str]] = []
    matched_specific = False

    for agent, directives in rules:
        if agent == bot_lower:
            candidates = directives
            matched_specific = True
            break
        if agent == "*" and not matched_specific:
            candidates = directives

    if not candidates:
        return True  # no applicable rule → allowed by default

    # Apply: for any directive matching "/", it's blanket; longest path wins.
    applicable: list[tuple[str, str]] = []
    for directive, path in candidates:
        if path == "" or path == "/":
            applicable.append((directive, "/"))
        elif path:
            applicable.append((directive, path))

    if not applicable:
        return True

    # Group: pick the longest path; Allow > Disallow on ties
    longest = max(len(p) for _, p in applicable)
    final = [d for d in applicable if len(d[1]) == longest]
    if any(d[0] == "disallow" for d in final):
        return False
    return True
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py -v
```

Expected: All tests PASS (the existing 7 + new 3).

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): robots.txt AI bot whitelist detection + tests"
```

---

### Task 3.4: Crawler — Composite `audit()` Method

**Files:**
- Modify: `D:/GEO2/backend/app/domain/crawler.py` (add `audit` method)
- Modify: `D:/GEO2/backend/tests/test_crawler.py` (add audit tests)

**Interfaces (additions):**
- `Crawler.audit(url: str) -> SiteAudit` — orchestrates fetch + extractions

- [ ] **Step 1: Append failing test**

Append to `D:/GEO2/backend/tests/test_crawler.py`:

```python
class TestCompositeAudit:
    @pytest.mark.asyncio
    @respx.mock
    async def test_audit_returns_full_site_audit(self, crawler: Crawler) -> None:
        respx.get("https://example.com").mock(
            return_value=Response(
                200,
                text='<html><head>'
                '<script type="application/ld+json">'
                '{"@type":"Organization","name":"X"}'
                '</script>'
                '</head><body>'
                '<h1>Title</h1><h2>S</h2>'
                '<p>Short para.</p>'
                '<a href="/about">About</a>'
                '</body></html>',
                headers={"content-type": "text/html", "last-modified": "Wed, 01 Jan 2026 00:00:00 GMT"},
            )
        )

        result = await crawler.audit("https://example.com")

        assert result.crawl_status == "success"
        assert result.schema.has_organization is True
        assert result.eeat.has_about_page is True
        assert result.structure.h1_count_ok is True
        assert result.freshness.has_publish_date is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_audit_marks_spa_as_partial(self, crawler: Crawler) -> None:
        """Empty <body> with a JS framework bundle is detected as SPA."""
        respx.get("https://spa.example.com").mock(
            return_value=Response(
                200,
                text='<html><head><script src="/bundle.js"></script></head>'
                '<body><div id="root"></div></body></html>',
            )
        )

        result = await crawler.audit("https://spa.example.com")

        assert result.crawl_status == "partial"

    @pytest.mark.asyncio
    @respx.mock
    async def test_audit_fails_on_timeout(self, crawler: Crawler) -> None:
        import httpx

        respx.get("https://dead.example.com").mock(side_effect=httpx.TimeoutException())

        with pytest.raises(Exception):
            await crawler.audit("https://dead.example.com")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py::TestCompositeAudit -v
```

Expected: FAIL with `AttributeError`

- [ ] **Step 3: Add `audit()` method to `crawler.py`**

Add to the `Crawler` class:

```python
    async def audit(self, url: str) -> "SiteAudit":
        """Composite audit: fetch + extract schema/eeat/structure/freshness.

        Raises CrawlError if the page cannot be reached at all.
        Marks result as 'partial' for SPA / near-empty pages.
        """
        from datetime import datetime, timezone

        from app.domain.exceptions import CrawlError
        from app.models.schemas import SiteAudit

        result = await self.fetch(url)
        if not result.success:
            raise CrawlError(reason=result.error or "unknown", url=url)

        # Heuristic SPA detection: empty body + JS bundle
        is_spa = (
            "<div id=\"root\"" in result.html
            or "<div id=\"app\"" in result.html
            or ("<body>" in result.html and "<p>" not in result.html and "<h1>" not in result.html)
        )

        # Fetch robots.txt (don't fail audit if it errors)
        robots = await self.fetch_robots_txt(url)
        bot_whitelist = self.check_ai_bot_whitelist(robots)

        return SiteAudit(
            url=url,
            crawl_status="partial" if is_spa else "success",
            crawled_at=datetime.now(timezone.utc),
            schema=self.extract_schema_coverage(result.html),
            eeat=self.extract_eeat_signals(result.html, url),
            structure=self.extract_structure(result.html),
            freshness=self.extract_freshness(result.html, None),
            page_load_ms=result.elapsed_ms,
            robots_txt_allows_ai_bots=bot_whitelist,
        )
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_crawler.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): composite site audit method + SPA detection + tests"
```

---

## Phase 4: Scoring Engine

### Task 4.1: Five-Dimension Scorer (TDD, IP-Critical)

**Files:**
- Create: `D:/GEO2/backend/app/domain/scorer.py`
- Create: `D:/GEO2/backend/tests/test_scorer.py`

**Interfaces:**
- Consumes: `SiteAudit`, `list[MentionResult]`
- Produces:
  - `compute_score_card(site_audit, mentions) -> ScoreCard`
  - `generate_suggestions(score_card, site_audit, mentions) -> list[Suggestion]`
  - `WEIGHTS` constant (dimension weights)

- [ ] **Step 1: Write failing tests**

Create `D:/GEO2/backend/tests/test_scorer.py`:

```python
"""Tests for the GEO scoring engine — IP-critical."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.scorer import WEIGHTS, compute_score_card, generate_suggestions
from app.models.schemas import (
    DimensionScore,
    EeatSignals,
    FreshnessScore,
    MentionResult,
    SchemaCoverage,
    SiteAudit,
    StructureScore,
)


def _make_audit(**overrides) -> SiteAudit:
    defaults = dict(
        url="https://example.com",
        crawl_status="success",
        crawled_at=datetime.now(timezone.utc),
        schema=SchemaCoverage(
            has_organization=True, has_website=True, has_faq=True,
            has_article=True, has_breadcrumb=True, has_product=False,
            detected_schemas=["Organization", "WebSite", "FAQPage", "Article", "BreadcrumbList"],
        ),
        eeat=EeatSignals(
            has_author_bio=True, has_contact_page=True, has_about_page=True,
            third_party_mentions=10, has_expert_attribution=True,
        ),
        structure=StructureScore(
            h1_count_ok=True, heading_hierarchy_valid=True,
            has_lists_or_tables=True, avg_paragraph_length=80,
            bluf_score=0.95,
        ),
        freshness=FreshnessScore(
            last_modified=datetime.now(timezone.utc) - timedelta(days=5),
            days_since_update=5, has_publish_date=True, has_recent_mention_in_content=True,
        ),
        page_load_ms=500,
        robots_txt_allows_ai_bots={"GPTBot": True, "ClaudeBot": True},
    )
    defaults.update(overrides)
    return SiteAudit(**defaults)


def _make_mention(mentioned: bool, position: int | None = 1) -> MentionResult:
    return MentionResult(
        question="q",
        llm_provider="deepseek",
        llm_answer="answer mentioning brand" if mentioned else "no brand here",
        brand_mentioned=mentioned,
        mention_position=position if mentioned else None,
    )


class TestWeights:
    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


class TestScoring:
    def test_perfect_site_with_full_mentions_high_score(self) -> None:
        audit = _make_audit()
        mentions = [_make_mention(mentioned=True) for _ in range(5)]
        card = compute_score_card(audit, mentions)

        assert card.overall >= 85
        assert card.mention_rate == 1.0
        assert card.avg_mention_position == 1.0

    def test_no_mentions_low_relevance(self) -> None:
        audit = _make_audit()
        mentions = [_make_mention(mentioned=False) for _ in range(5)]
        card = compute_score_card(audit, mentions)

        assert card.relevance.score <= 2.0
        assert card.mention_rate == 0.0

    def test_partial_failures_excluded_from_rate(self) -> None:
        audit = _make_audit()
        mentions = [
            _make_mention(mentioned=True),
            _make_mention(mentioned=False),
            MentionResult(question="q", llm_provider="deepseek", llm_answer="",
                          brand_mentioned=False, error="timeout"),
            MentionResult(question="q", llm_provider="deepseek", llm_answer="",
                          brand_mentioned=False, error="timeout"),
        ]
        card = compute_score_card(audit, mentions)

        # 2 valid samples, 1 mentioned → rate = 0.5
        assert card.mention_rate == 0.5

    def test_overall_is_weighted_sum(self) -> None:
        audit = _make_audit()
        mentions = [_make_mention(mentioned=True) for _ in range(3)]
        card = compute_score_card(audit, mentions)

        expected = sum(
            getattr(card, dim).score * getattr(card, dim).weight
            for dim in ["authority", "relevance", "structure", "freshness", "verifiability"]
        ) * 10
        assert abs(card.overall - expected) < 0.01


class TestSuggestions:
    def test_suggests_schema_when_missing(self) -> None:
        audit = _make_audit(schema=SchemaCoverage(has_organization=False, detected_schemas=[]))
        mentions = [_make_mention(mentioned=False)]
        card = compute_score_card(audit, mentions)
        suggestions = generate_suggestions(card, audit, mentions)

        titles = [s.title for s in suggestions]
        assert any("Schema" in t or "结构化" in t for t in titles)

    def test_suggests_bluf_when_score_low(self) -> None:
        audit = _make_audit(structure=StructureScore(h1_count_ok=True, bluf_score=0.2))
        mentions = [_make_mention(mentioned=True)]
        card = compute_score_card(audit, mentions)
        suggestions = generate_suggestions(card, audit, mentions)

        assert any("BLUF" in s.title or "结论先行" in s.title for s in suggestions)

    def test_suggests_ai_bot_blocked(self) -> None:
        audit = _make_audit(robots_txt_allows_ai_bots={"GPTBot": False, "ClaudeBot": True})
        mentions = []
        card = compute_score_card(audit, mentions)
        suggestions = generate_suggestions(card, audit, mentions)

        assert any("robots.txt" in s.title or "爬虫" in s.title for s in suggestions)
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_scorer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `app/domain/scorer.py`**

Create `D:/GEO2/backend/app/domain/scorer.py`:

```python
"""Five-dimension GEO scoring engine.

Dimensions (weights in `WEIGHTS`):
  - authority (0.25): E-E-A-T signals
  - relevance (0.30): AI mention rate
  - structure (0.20): heading hierarchy, BLUF, paragraph length
  - freshness (0.15): content update frequency
  - verifiability (0.10): schema + structured data coverage

Each dimension is scored 0-10. Overall = weighted sum * 10 (range 0-100).
"""
from __future__ import annotations

from app.models.schemas import (
    DimensionScore,
    EeatSignals,
    FreshnessScore,
    MentionResult,
    SchemaCoverage,
    ScoreCard,
    SiteAudit,
    StructureScore,
    Suggestion,
)

WEIGHTS: dict[str, float] = {
    "authority": 0.25,
    "relevance": 0.30,
    "structure": 0.20,
    "freshness": 0.15,
    "verifiability": 0.10,
}


def _score_authority(audit: SiteAudit) -> DimensionScore:
    """Score based on EEAT signals (0-10)."""
    eeat: EeatSignals = audit.eeat
    score = 0.0
    evidence: list[str] = []

    if eeat.has_about_page:
        score += 2
        evidence.append("有 About 页面")
    if eeat.has_contact_page:
        score += 2
        evidence.append("有 Contact 页面")
    if eeat.has_author_bio:
        score += 2
        evidence.append("有作者署名")
    if eeat.has_expert_attribution:
        score += 1
        evidence.append("有专家背书")
    # 3rd party mentions: scale 0-10 mentions → 0-3 points
    third_party_pts = min(eeat.third_party_mentions / 10 * 3, 3)
    score += third_party_pts
    if third_party_pts > 0:
        evidence.append(f"第三方权威源提及 {eeat.third_party_mentions} 次")

    return DimensionScore(
        name="权威度",
        score=min(score, 10),
        weight=WEIGHTS["authority"],
        evidence=evidence,
    )


def _score_relevance(mentions: list[MentionResult]) -> DimensionScore:
    """Score based on AI mention rate (0-10)."""
    valid = [m for m in mentions if m.error is None]
    evidence: list[str] = []

    if not valid:
        return DimensionScore(
            name="内容相关性", score=0, weight=WEIGHTS["relevance"],
            evidence=["无有效 LLM 样本"],
        )

    mentioned = [m for m in valid if m.brand_mentioned]
    rate = len(mentioned) / len(valid)
    # Linear: 100% mention → 10, 0% → 0
    base_score = rate * 10

    evidence.append(f"AI 提及率 {rate*100:.0f}% ({len(mentioned)}/{len(valid)})")
    if mentioned:
        avg_pos = sum(m.mention_position or 99 for m in mentioned) / len(mentioned)
        evidence.append(f"平均提及位置 {avg_pos:.1f}")
        # Bonus for early mention
        if avg_pos <= 2:
            base_score = min(base_score + 0.5, 10)

    return DimensionScore(
        name="内容相关性", score=base_score, weight=WEIGHTS["relevance"], evidence=evidence,
    )


def _score_structure(audit: SiteAudit) -> DimensionScore:
    """Score based on heading hierarchy + BLUF (0-10)."""
    s: StructureScore = audit.structure
    score = 0.0
    evidence: list[str] = []

    if s.h1_count_ok:
        score += 3
        evidence.append("H1 数量正确 (1个)")
    if s.heading_hierarchy_valid:
        score += 2
        evidence.append("标题层级合规 (H1→H2→H3)")
    if s.has_lists_or_tables:
        score += 2
        evidence.append("使用了列表或表格")
    # BLUF
    score += s.bluf_score * 3
    if s.bluf_score >= 0.8:
        evidence.append("结论先行 (BLUF) 评分高")

    return DimensionScore(
        name="内容结构", score=min(score, 10), weight=WEIGHTS["structure"], evidence=evidence,
    )


def _score_freshness(audit: SiteAudit) -> DimensionScore:
    """Score based on content update recency (0-10)."""
    f: FreshnessScore = audit.freshness
    score = 0.0
    evidence: list[str] = []

    if f.days_since_update is None:
        evidence.append("无法判断更新时间")
        return DimensionScore(
            name="更新频率", score=2, weight=WEIGHTS["freshness"], evidence=evidence,
        )

    days = f.days_since_update
    if days <= 7:
        score = 10
        evidence.append(f"{days} 天前更新（极新鲜）")
    elif days <= 30:
        score = 8
        evidence.append(f"{days} 天前更新（新鲜）")
    elif days <= 90:
        score = 5
        evidence.append(f"{days} 天前更新（中等）")
    elif days <= 365:
        score = 3
        evidence.append(f"{days} 天前更新（陈旧）")
    else:
        score = 1
        evidence.append(f"{days} 天前更新（非常陈旧）")

    if f.has_recent_mention_in_content:
        score = min(score + 1, 10)
        evidence.append("内容中提及当年/最新年份")

    return DimensionScore(
        name="更新频率", score=score, weight=WEIGHTS["freshness"], evidence=evidence,
    )


def _score_verifiability(audit: SiteAudit) -> DimensionScore:
    """Score based on structured data coverage (0-10)."""
    s: SchemaCoverage = audit.schema
    detected = len(s.detected_schemas)
    score = min(detected * 2, 10)
    evidence = [f"已部署 {detected} 种 Schema: {', '.join(s.detected_schemas) or '无'}"]

    # Penalty if AI bots blocked
    blocked_bots = [b for b, allowed in audit.robots_txt_allows_ai_bots.items() if not allowed]
    if blocked_bots:
        score = max(score - 2, 0)
        evidence.append(f"⚠️ 以下 AI 爬虫被 robots.txt 屏蔽: {', '.join(blocked_bots)}")

    return DimensionScore(
        name="数据可验证性", score=score, weight=WEIGHTS["verifiability"], evidence=evidence,
    )


def compute_score_card(
    site_audit: SiteAudit | None,
    mentions: list[MentionResult],
) -> ScoreCard:
    """Compute the five-dimension score card.

    If site_audit is None (crawl failed), structure/freshness/etc default to 0.
    """
    if site_audit is None:
        # Cannot score site-dependent dimensions
        empty = DimensionScore(name="x", score=0, weight=0, evidence=[])
        return ScoreCard(
            authority=empty, relevance=empty, structure=empty,
            freshness=empty, verifiability=empty,
            overall=0, mention_rate=0.0, avg_mention_position=None,
        )

    authority = _score_authority(site_audit)
    relevance = _score_relevance(mentions)
    structure = _score_structure(site_audit)
    freshness = _score_freshness(site_audit)
    verifiability = _score_verifiability(site_audit)

    overall = (
        authority.score * authority.weight
        + relevance.score * relevance.weight
        + structure.score * structure.weight
        + freshness.score * freshness.weight
        + verifiability.score * verifiability.weight
    ) * 10

    # Mention rate / avg position
    valid = [m for m in mentions if m.error is None]
    mentioned = [m for m in valid if m.brand_mentioned]
    rate = len(mentioned) / len(valid) if valid else 0.0
    avg_pos = (
        sum(m.mention_position for m in mentioned if m.mention_position is not None)
        / len(mentioned)
        if mentioned else None
    )

    return ScoreCard(
        authority=authority, relevance=relevance, structure=structure,
        freshness=freshness, verifiability=verifiability,
        overall=overall, mention_rate=rate, avg_mention_position=avg_pos,
    )


def generate_suggestions(
    card: ScoreCard,
    audit: SiteAudit | None,
    mentions: list[MentionResult],
) -> list[Suggestion]:
    """Produce actionable suggestions based on the scorecard."""
    suggestions: list[Suggestion] = []

    # Schema-related
    if audit and len(audit.schema.detected_schemas) < 3:
        suggestions.append(Suggestion(
            priority="P0",
            category="schema",
            title="部署基础 Schema.org 结构化数据",
            detail=(
                "当前页面缺少 Organization / WebSite / Article 等基础结构化数据。"
                "AI 引擎在解析页面时无法可靠识别品牌实体。"
            ),
            action_steps=[
                "在 <head> 中添加 Organization JSON-LD（包含 name、url、logo）",
                "为关键页面添加 WebSite 和 BreadcrumbList",
                "使用 Google Rich Results Test 验证部署",
            ],
            expected_impact="提升 AI 引擎对品牌实体的识别度，预计整体评分 +5-10 分",
        ))

    # AI bots blocked
    if audit:
        blocked = [b for b, ok in audit.robots_txt_allows_ai_bots.items() if not ok]
        if blocked:
            suggestions.append(Suggestion(
                priority="P0",
                category="robots",
                title="放开 AI 爬虫的 robots.txt 限制",
                detail=(
                    f"当前 robots.txt 屏蔽了 {len(blocked)} 个 AI 爬虫 "
                    f"({', '.join(blocked)})，导致这些引擎无法抓取您的内容。"
                ),
                action_steps=[
                    f"在 robots.txt 中为 {', '.join(blocked)} 添加 Allow: /",
                    "或使用 User-agent: * 配合 Allow: / 全局放开",
                ],
                expected_impact="让被屏蔽的 AI 引擎能够抓取并引用您的内容",
            ))

    # Mention rate low
    valid = [m for m in mentions if m.error is None]
    if valid:
        rate = len([m for m in valid if m.brand_mentioned]) / len(valid)
        if rate < 0.5:
            suggestions.append(Suggestion(
                priority="P0",
                category="content",
                title="提升品牌在 AI 答案中的提及率",
                detail=(
                    f"在测试的 {len(valid)} 个问题中，AI 仅在 {rate*100:.0f}% 的答案中"
                    f"提到了您的品牌。需要让品牌信息在 AI 训练/检索数据中更突出。"
                ),
                action_steps=[
                    "在官网发布结构化的 FAQ，覆盖用户常问的问题",
                    "在权威第三方平台（知乎、微信公众号、行业媒体）发布带品牌的深度内容",
                    "为关键产品页添加 HowTo 和 FAQPage Schema",
                ],
                expected_impact="提升 AI 引用权重，预计提及率提升 20-40%",
            ))

    # BLUF
    if audit and audit.structure.bluf_score < 0.6:
        suggestions.append(Suggestion(
            priority="P1",
            category="structure",
            title="使用 BLUF（结论先行）写作结构",
            detail=(
                "您的内容未在开头给出明确结论。AI 引擎倾向于引用"
                "段落级别独立可读的句子——结论埋得越深，越难被引用。"
            ),
            action_steps=[
                "在每篇文章前 100 字内给出核心结论",
                "每段第一句话必须是该段的核心主张",
                "避免大段铺垫，直接回答'是什么 / 为什么 / 怎么做'",
            ],
            expected_impact="段落级引用概率显著提升",
        ))

    # Freshness
    if audit and audit.freshness.days_since_update is not None and audit.freshness.days_since_update > 90:
        suggestions.append(Suggestion(
            priority="P1",
            category="freshness",
            title="更新陈旧内容",
            detail=(
                f"核心内容已 {audit.freshness.days_since_update} 天未更新。"
                "AI 引擎会降低对陈旧内容的引用权重。"
            ),
            action_steps=[
                "为关键页面设置 30 天更新一次的节奏",
                "添加 datePublished 和 dateModified 元数据",
                "在内容中提及当前年份以表明时效性",
            ],
            expected_impact="新鲜度评分提升 3-5 分",
        ))

    # Authority
    if audit and not audit.eeat.has_author_bio:
        suggestions.append(Suggestion(
            priority="P1",
            category="eeat",
            title="添加作者署名和专业背景",
            detail=(
                "页面缺少明确的作者信息和专业背景。"
                "E-E-A-T 中 Experience 和 Expertise 信号不足。"
            ),
            action_steps=[
                "为每篇文章添加作者署名 + 个人简介",
                "作者简介中体现行业经验和资质",
                "在 About 页面展示团队专业背景",
            ],
            expected_impact="权威度评分提升 2-3 分",
        ))

    return suggestions
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_scorer.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): five-dimension scoring engine with suggestions + comprehensive tests"
```

---

## Phase 5: Report Rendering

### Task 5.1: Jinja2 + WeasyPrint PDF Renderer

**Files:**
- Create: `D:/GEO2/backend/app/domain/__init__.py` (already exists)
- Create: `D:/GEO2/backend/app/domain/renderer.py`
- Create: `D:/GEO2/backend/app/templates/__init__.py`
- Create: `D:/GEO2/backend/app/templates/report.html.j2`
- Create: `D:/GEO2/backend/app/templates/report.css`
- Create: `D:/GEO2/backend/tests/test_renderer.py`

**Interfaces:**
- Consumes: `Report`, `data/reports/` directory
- Produces:
  - `render_html(report: Report) -> str` — returns rendered HTML
  - `render_pdf(report: Report, output_path: str) -> str` — writes PDF, returns path

- [ ] **Step 1: Create `templates/__init__.py`**

Create empty `D:/GEO2/backend/app/templates/__init__.py`.

- [ ] **Step 2: Create `templates/report.css`**

Create `D:/GEO2/backend/app/templates/report.css`:

```css
@page {
  size: A4;
  margin: 20mm 15mm;
}

body {
  font-family: "Noto Sans CJK SC", -apple-system, sans-serif;
  font-size: 11pt;
  color: #1f2937;
  line-height: 1.5;
}

h1 {
  font-size: 24pt;
  color: #111827;
  margin: 0 0 8pt;
  border-bottom: 2px solid #2563eb;
  padding-bottom: 8pt;
}

h2 {
  font-size: 16pt;
  color: #1f2937;
  margin: 16pt 0 8pt;
}

.score-overall {
  font-size: 36pt;
  font-weight: bold;
  color: #2563eb;
  text-align: center;
  margin: 12pt 0;
}

.dimension {
  margin: 6pt 0;
  padding: 6pt 10pt;
  background: #f3f4f6;
  border-left: 3px solid #2563eb;
}

.dimension-name { font-weight: bold; }
.dimension-score { float: right; color: #2563eb; }

.evidence { font-size: 9pt; color: #6b7280; margin-top: 2pt; }

.suggestion {
  margin: 8pt 0;
  padding: 8pt 12pt;
  border: 1px solid #e5e7eb;
  border-radius: 4pt;
}

.suggestion.P0 { border-left: 4pt solid #dc2626; }
.suggestion.P1 { border-left: 4pt solid #f59e0b; }
.suggestion.P2 { border-left: 4pt solid #10b981; }

.suggestion-title { font-weight: bold; margin-bottom: 4pt; }
.suggestion-steps { margin: 4pt 0 0 16pt; font-size: 10pt; }

table { width: 100%; border-collapse: collapse; margin: 8pt 0; }
th, td { border: 1px solid #e5e7eb; padding: 4pt 8pt; text-align: left; }
th { background: #f9fafb; }

.summary {
  background: #eff6ff;
  padding: 10pt;
  border-radius: 4pt;
  margin: 12pt 0;
}
```

- [ ] **Step 3: Create `templates/report.html.j2`**

Create `D:/GEO2/backend/app/templates/report.html.j2`:

```jinja
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>GEO 诊断报告 - {{ report.brand.name }}</title>
  <link rel="stylesheet" href="report.css">
</head>
<body>
  <h1>GEO 诊断报告</h1>
  <p><strong>品牌：</strong>{{ report.brand.name }} ({{ report.brand.industry }})<br>
     <strong>官网：</strong>{{ report.brand.official_url }}<br>
     <strong>生成时间：</strong>{{ report.created_at.strftime('%Y-%m-%d %H:%M UTC') }}</p>

  <div class="summary">
    <h2>执行摘要</h2>
    <p>{{ report.summary }}</p>
  </div>

  <div class="score-overall">{{ "%.1f"|format(report.score_card.overall) }}<span style="font-size:14pt;">/100</span></div>

  <h2>五维度评分</h2>
  {% for dim in [report.score_card.authority, report.score_card.relevance, report.score_card.structure, report.score_card.freshness, report.score_card.verifiability] %}
  <div class="dimension">
    <span class="dimension-name">{{ dim.name }}</span>
    <span class="dimension-score">{{ "%.1f"|format(dim.score) }}/10 (权重 {{ "%.0f%%"|format(dim.weight * 100) }})</span>
    {% for ev in dim.evidence %}
    <div class="evidence">• {{ ev }}</div>
    {% endfor %}
  </div>
  {% endfor %}

  <h2>AI 提及率</h2>
  <table>
    <thead><tr><th>问题</th><th>LLM</th><th>提及</th><th>位置</th><th>情感</th></tr></thead>
    <tbody>
      {% for m in report.mentions %}
      <tr>
        <td>{{ m.question }}</td>
        <td>{{ m.llm_provider }}</td>
        <td>{{ '是' if m.brand_mentioned else '否' }}</td>
        <td>{{ m.mention_position or '-' }}</td>
        <td>{{ m.sentiment }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>优化建议 ({{ report.suggestions|length }} 条)</h2>
  {% for s in report.suggestions %}
  <div class="suggestion {{ s.priority }}">
    <div class="suggestion-title">[{{ s.priority }}] {{ s.title }}</div>
    <div>{{ s.detail }}</div>
    {% if s.action_steps %}
    <ul class="suggestion-steps">
      {% for step in s.action_steps %}
      <li>{{ step }}</li>
      {% endfor %}
    </ul>
    {% endif %}
    <div class="evidence"><strong>预期效果：</strong>{{ s.expected_impact }}</div>
  </div>
  {% endfor %}

  {% if report.site_audit and report.site_audit.crawl_status == 'partial' %}
  <div class="summary" style="background:#fef3c7;">
    <strong>⚠️ 注意：</strong>该网站为单页应用 (SPA)，爬虫无法读取 JS 渲染后的内容，诊断结果仅供参考。
  </div>
  {% endif %}
</body>
</html>
```

- [ ] **Step 4: Write failing test**

Create `D:/GEO2/backend/tests/test_renderer.py`:

```python
"""Tests for the report renderer."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from app.domain.renderer import render_html, render_pdf
from app.models.schemas import (
    BrandInfo,
    DimensionScore,
    MentionResult,
    Report,
    ScoreCard,
    SiteAudit,
    Suggestion,
)


@pytest.fixture
def sample_report() -> Report:
    return Report(
        id="r1", task_id="t1",
        brand=BrandInfo(name="小米", industry="手机", official_url="https://www.mi.com"),
        site_audit=SiteAudit(
            url="https://www.mi.com", crawl_status="success",
            crawled_at=datetime.now(timezone.utc),
        ),
        mentions=[
            MentionResult(
                question="手机推荐", llm_provider="deepseek",
                llm_answer="小米不错", brand_mentioned=True,
                mention_position=1, sentiment="positive",
            ),
        ],
        score_card=ScoreCard(
            authority=DimensionScore(name="权威度", score=8.0, weight=0.25, evidence=[]),
            relevance=DimensionScore(name="相关性", score=7.0, weight=0.30, evidence=[]),
            structure=DimensionScore(name="结构", score=6.0, weight=0.20, evidence=[]),
            freshness=DimensionScore(name="新鲜", score=9.0, weight=0.15, evidence=[]),
            verifiability=DimensionScore(name="可验证", score=5.0, weight=0.10, evidence=[]),
            overall=72.5, mention_rate=1.0, avg_mention_position=1.0,
        ),
        suggestions=[
            Suggestion(
                priority="P0", category="schema", title="测试建议",
                detail="详情", action_steps=["步骤1"], expected_impact="效果",
            ),
        ],
        summary="这是摘要",
        created_at=datetime.now(timezone.utc),
    )


class TestRenderHtml:
    def test_returns_string(self, sample_report: Report) -> None:
        html = render_html(sample_report)
        assert isinstance(html, str)
        assert "小米" in html
        assert "GEO 诊断报告" in html
        assert "测试建议" in html


class TestRenderPdf:
    def test_writes_pdf_file(self, sample_report: Report) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "report.pdf")
            result_path = render_pdf(sample_report, out)

            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 1000  # non-empty PDF

            # Verify it's a PDF
            with open(result_path, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-"
```

- [ ] **Step 5: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_renderer.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 6: Create `app/domain/renderer.py`**

Create `D:/GEO2/backend/app/domain/renderer.py`:

```python
"""HTML + PDF report renderer using Jinja2 and WeasyPrint."""
from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML

from app.models.schemas import Report

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _get_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,
    )


def render_html(report: Report) -> str:
    """Render report to HTML string using Jinja2 template."""
    env = _get_env()
    template = env.get_template("report.html.j2")
    return template.render(report=report)


def render_pdf(report: Report, output_path: str) -> str:
    """Render report to PDF file. Returns the output path."""
    html_str = render_html(report)
    css_path = _TEMPLATE_DIR / "report.css"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    html = HTML(string=html_str, base_url=str(_TEMPLATE_DIR))
    html.write_pdf(output_path, stylesheets=[CSS(filename=str(css_path))])
    return output_path
```

- [ ] **Step 7: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_renderer.py -v
```

Expected: Both tests PASS.

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): Jinja2 + WeasyPrint report renderer with PDF + tests"
```

---

## Phase 6: Service Layer

### Task 6.1: DiagnosisService — Orchestration

**Files:**
- Create: `D:/GEO2/backend/app/services/__init__.py`
- Create: `D:/GEO2/backend/app/services/diagnosis_service.py`
- Create: `D:/GEO2/backend/tests/test_diagnosis_service.py`

**Interfaces:**
- Consumes: `ReportRepository`, `Crawler`, `LLMClient`
- Produces:
  - `DiagnosisService.run(task_id, request) -> None` — executes the full pipeline; updates DB at each stage

- [ ] **Step 1: Create `services/__init__.py`**

Create empty `D:/GEO2/backend/app/services/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_diagnosis_service.py`:

```python
"""Tests for the DiagnosisService orchestration."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.domain.crawler import Crawler
from app.domain.llm_client import LLMClient
from app.models.schemas import (
    DiagnosisRequest,
    DimensionScore,
    EeatSignals,
    FreshnessScore,
    MentionResult,
    SchemaCoverage,
    ScoreCard,
    SiteAudit,
    StructureScore,
)
from app.services.diagnosis_service import DiagnosisService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        deepseek_api_key="sk-test",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        llm_call_timeout_s=5,
    )


@pytest.fixture
def mock_audit() -> SiteAudit:
    from datetime import datetime, timezone
    return SiteAudit(
        url="https://example.com", crawl_status="success",
        crawled_at=datetime.now(timezone.utc),
        schema=SchemaCoverage(has_organization=True, detected_schemas=["Organization"]),
        eeat=EeatSignals(has_about_page=True),
        structure=StructureScore(h1_count_ok=True, bluf_score=0.8),
        freshness=FreshnessScore(days_since_update=10, has_publish_date=True),
        robots_txt_allows_ai_bots={"GPTBot": True},
    )


@pytest.fixture
def mock_mentions() -> list[MentionResult]:
    return [
        MentionResult(question="q1", llm_provider="deepseek", llm_answer="ok",
                      brand_mentioned=True, mention_position=1),
    ]


@pytest.mark.asyncio
async def test_run_completes_through_all_stages(
    db_session, settings, mock_audit, mock_mentions
) -> None:
    from app.repositories.report_repo import ReportRepository

    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["q1", "q2", "q3"],
    )
    row = await repo.create(req)

    # Mock collaborators
    crawler = AsyncMock(spec=Crawler)
    crawler.audit = AsyncMock(return_value=mock_audit)

    llm = AsyncMock(spec=LLMClient)
    llm.query_mentions = AsyncMock(return_value=mock_mentions)

    svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)

    await svc.run(row.task_id, req)

    final = await repo.get_by_task_id(row.task_id)
    assert final.status == "completed"
    assert final.progress == 100
    assert final.report_json is not None
    assert final.pdf_path is None  # PDF rendering is opt-in (separate path)


@pytest.mark.asyncio
async def test_run_marks_failed_on_crawl_error(
    db_session, settings, mock_audit
) -> None:
    from app.domain.exceptions import CrawlError
    from app.repositories.report_repo import ReportRepository

    repo = ReportRepository(db_session)
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://dead.example.com",
        target_questions=["q1", "q2", "q3"],
    )
    row = await repo.create(req)

    crawler = AsyncMock(spec=Crawler)
    crawler.audit = AsyncMock(side_effect=CrawlError(reason="DNS", url="https://dead.example.com"))
    llm = AsyncMock(spec=LLMClient)

    svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)
    await svc.run(row.task_id, req)

    final = await repo.get_by_task_id(row.task_id)
    assert final.status == "failed"
    assert final.error_message is not None
    assert "DNS" in final.error_message
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_diagnosis_service.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Create `services/diagnosis_service.py`**

Create `D:/GEO2/backend/app/services/diagnosis_service.py`:

```python
"""Orchestrates the full diagnosis pipeline for one task."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.core.config import Settings
from app.domain.crawler import Crawler
from app.domain.exceptions import CrawlError, DomainError, LlmError, RenderError, ScoreError
from app.domain.llm_client import LLMClient
from app.domain.renderer import render_pdf
from app.domain.scorer import compute_score_card, generate_suggestions
from app.models.schemas import (
    BrandInfo,
    DiagnosisRequest,
    Report,
    SiteAudit,
)
from app.repositories.report_repo import ReportRepository

logger = structlog.get_logger()


class DiagnosisService:
    """Runs the full diagnosis pipeline for one task."""

    def __init__(
        self,
        repo: ReportRepository,
        crawler: Crawler,
        llm: LLMClient,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.crawler = crawler
        self.llm = llm
        self.settings = settings

    async def run(self, task_id: str, req: DiagnosisRequest) -> None:
        """Execute pipeline: crawl → LLM → score → save report.

        Updates DB at each stage. On failure, marks task as failed.
        """
        try:
            # Stage 1: Crawl
            await self.repo.update_status(task_id, status="crawling", progress=10)
            site_audit: SiteAudit | None = None
            try:
                site_audit = await self.crawler.audit(str(req.official_url))
            except CrawlError as e:
                logger.error("crawl_failed", task_id=task_id, error=str(e))
                await self.repo.update_status(
                    task_id, status="failed", progress=0, error=f"官网无法访问：{e.reason}"
                )
                return

            # Stage 2: LLM
            await self.repo.update_status(task_id, status="querying_llm", progress=30)
            mentions = await self.llm.query_mentions(
                brand=req.brand_name,
                industry=req.industry,
                questions=req.target_questions,
            )
            logger.info("llm_done", task_id=task_id, n_mentions=len(mentions))

            # Stage 3: Scoring
            await self.repo.update_status(task_id, status="scoring", progress=70)
            card = compute_score_card(site_audit, mentions)
            suggestions = generate_suggestions(card, site_audit, mentions)
            summary = await self._generate_summary(req, card)

            # Stage 4: Build report
            await self.repo.update_status(task_id, status="rendering", progress=90)
            report = Report(
                id=task_id,
                task_id=task_id,
                brand=BrandInfo(
                    name=req.brand_name,
                    industry=req.industry,
                    official_url=str(req.official_url),
                ),
                site_audit=site_audit,
                mentions=mentions,
                score_card=card,
                suggestions=suggestions,
                summary=summary,
                created_at=datetime.now(timezone.utc),
                pdf_available=False,
            )

            # Save HTML report to DB (PDF is generated on-demand in API)
            report_json = report.model_dump_json()
            await self.repo.update_report(task_id, report_json=report_json)

            await self.repo.update_status(task_id, status="completed", progress=100)
            logger.info("diagnosis_completed", task_id=task_id, overall=card.overall)

        except DomainError as e:
            logger.exception("domain_error", task_id=task_id)
            await self.repo.update_status(
                task_id, status="failed", progress=0, error=f"{type(e).__name__}: {e}"
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("unexpected_error", task_id=task_id)
            await self.repo.update_status(
                task_id, status="failed", progress=0, error=f"unexpected: {type(e).__name__}"
            )

    async def _generate_summary(self, req: DiagnosisRequest, card) -> str:
        """Generate executive summary via LLM. Falls back to template on failure."""
        try:
            prompt = (
                f"品牌「{req.brand_name}」({req.industry}) 的 GEO 诊断总分为 "
                f"{card.overall:.1f}/100。请用 2-3 句话给出执行摘要，"
                f"指出最重要的 1-2 个改进方向。语言：简体中文。"
            )
            # Use DeepSeek directly for summary
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                timeout=15,
            )
            response = await client.chat.completions.create(
                model=self.settings.deepseek_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )
            return response.choices[0].message.content or _fallback_summary(card)
        except Exception:  # noqa: BLE001
            return _fallback_summary(card)


def _fallback_summary(card) -> str:
    score = card.overall
    if score >= 80:
        return f"品牌 GEO 健康度优秀（{score:.1f}/100），建议持续维护并监控趋势。"
    if score >= 60:
        return f"品牌 GEO 健康度良好（{score:.1f}/100），有明确的改进空间。"
    if score >= 40:
        return f"品牌 GEO 健康度中等（{score:.1f}/100），需要系统性优化。"
    return f"品牌 GEO 健康度较弱（{score:.1f}/100），建议优先处理 P0 级建议。"
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_diagnosis_service.py -v
```

Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): DiagnosisService orchestration with stage tracking + tests"
```

---

### Task 6.2: PDF On-Demand Rendering

**Files:**
- Create: `D:/GEO2/backend/app/services/report_service.py`
- Create: `D:/GEO2/backend/tests/test_report_service.py`

**Interfaces:**
- Consumes: `ReportRepository`, `domain.renderer`
- Produces:
  - `ReportService.get_or_render_pdf(report_id) -> str` — returns path, generates if missing

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_report_service.py`:

```python
"""Tests for report retrieval + on-demand PDF rendering."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.models.schemas import (
    BrandInfo, DimensionScore, MentionResult, Report, ScoreCard,
    SiteAudit, Suggestion,
)
from app.repositories.report_repo import ReportRepository
from app.services.report_service import ReportService


@pytest.fixture
def sample_report_dict() -> dict:
    return {
        "id": "test-id",
        "task_id": "test-id",
        "brand": {"name": "X", "industry": "Y", "official_url": "https://example.com"},
        "site_audit": {
            "url": "https://example.com", "crawl_status": "success",
            "crawled_at": "2026-01-01T00:00:00Z",
            "schema": {}, "eeat": {}, "structure": {}, "freshness": {},
            "page_load_ms": None, "robots_txt_allows_ai_bots": {},
        },
        "mentions": [],
        "score_card": {
            "authority": {"name": "a", "score": 5, "weight": 0.25, "evidence": []},
            "relevance": {"name": "r", "score": 5, "weight": 0.30, "evidence": []},
            "structure": {"name": "s", "score": 5, "weight": 0.20, "evidence": []},
            "freshness": {"name": "f", "score": 5, "weight": 0.15, "evidence": []},
            "verifiability": {"name": "v", "score": 5, "weight": 0.10, "evidence": []},
            "overall": 50.0, "mention_rate": 0.0, "avg_mention_position": None,
        },
        "suggestions": [],
        "summary": "s",
        "created_at": "2026-01-01T00:00:00Z",
        "pdf_available": False,
    }


@pytest.mark.asyncio
async def test_get_pdf_renders_if_missing(db_session, sample_report_dict) -> None:
    repo = ReportRepository(db_session)
    from app.models.schemas import DiagnosisRequest
    req = DiagnosisRequest(
        brand_name="X", industry="Y", official_url="https://example.com",
        target_questions=["a", "b", "c"],
    )
    row = await repo.create(req)
    import json
    await repo.update_report(row.task_id, json.dumps(sample_report_dict))

    with tempfile.TemporaryDirectory() as tmp:
        # Patch data path
        with patch("app.services.report_service.PDF_DIR", tmp):
            svc = ReportService(repo=repo)
            pdf_path = await svc.get_or_render_pdf(row.task_id)

            assert os.path.exists(pdf_path)
            assert pdf_path.endswith(".pdf")
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_report_service.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `services/report_service.py`**

Create `D:/GEO2/backend/app/services/report_service.py`:

```python
"""Report retrieval + on-demand PDF rendering."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.domain.renderer import render_pdf
from app.models.schemas import Report
from app.repositories.report_repo import ReportRepository

PDF_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"


class ReportService:
    """Provides access to stored reports + PDF rendering."""

    def __init__(self, repo: ReportRepository) -> None:
        self.repo = repo

    async def get_report(self, task_id: str) -> Report | None:
        """Load completed report by task_id. Returns None if not found or not done."""
        row = await self.repo.get_by_task_id(task_id)
        if row is None or row.report_json is None:
            return None
        data = json.loads(row.report_json)
        return Report(**data)

    async def list_summaries(self, limit: int = 50) -> list[dict]:
        """Return lightweight summaries for the report list page."""
        rows = await self.repo.list_recent(limit=limit)
        return [
            {
                "id": r.id,
                "brand_name": r.brand_name,
                "industry": r.industry,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "overall_score": _extract_overall(r.report_json),
            }
            for r in rows
        ]

    async def get_or_render_pdf(self, task_id: str) -> str:
        """Return PDF path; render if not yet on disk."""
        row = await self.repo.get_by_task_id(task_id)
        if row is None or row.report_json is None:
            raise FileNotFoundError(f"Report {task_id} not found or not completed")

        pdf_dir = PDF_DIR
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / f"{task_id}.pdf"

        if pdf_path.exists():
            return str(pdf_path)

        report = Report(**json.loads(row.report_json))
        render_pdf(report, str(pdf_path))

        # Update DB with path
        await self.repo.update_report(task_id, row.report_json, pdf_path=str(pdf_path))
        return str(pdf_path)


def _extract_overall(report_json: str | None) -> float | None:
    if not report_json:
        return None
    try:
        data = json.loads(report_json)
        return data.get("score_card", {}).get("overall")
    except (json.JSONDecodeError, KeyError):
        return None
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_report_service.py -v
```

Expected: Test PASSES.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): ReportService with on-demand PDF rendering + tests"
```

---

## Phase 7: API Layer

### Task 7.1: POST /api/diagnosis Endpoint

**Files:**
- Create: `D:/GEO2/backend/app/api/__init__.py`
- Create: `D:/GEO2/backend/app/api/diagnosis.py`
- Modify: `D:/GEO2/backend/app/main.py` (register router)
- Create: `D:/GEO2/backend/tests/test_api.py`

**Interfaces:**
- Consumes: `DiagnosisRequest` (body), `ReportRepository` (DI)
- Produces:
  - `POST /api/diagnosis` → 202 + `{ task_id, status: "pending" }`

- [ ] **Step 1: Create `api/__init__.py`**

Create empty `D:/GEO2/backend/app/api/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_api.py`:

```python
"""Integration tests for the FastAPI app."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    """Health check still works."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_post_diagnosis_returns_202_and_task_id(client: TestClient) -> None:
    resp = client.post(
        "/api/diagnosis",
        json={
            "brand_name": "测试",
            "industry": "电商",
            "official_url": "https://example.com",
            "target_questions": ["q1", "q2", "q3"],
        },
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "task_id" in body
    assert body["status"] == "pending"


def test_post_diagnosis_validates_url(client: TestClient) -> None:
    resp = client.post(
        "/api/diagnosis",
        json={
            "brand_name": "x",
            "industry": "y",
            "official_url": "not-a-url",
            "target_questions": ["q1", "q2", "q3"],
        },
    )
    assert resp.status_code == 422


def test_get_status_returns_task(client: TestClient) -> None:
    create = client.post(
        "/api/diagnosis",
        json={
            "brand_name": "X", "industry": "Y",
            "official_url": "https://example.com",
            "target_questions": ["a", "b", "c"],
        },
    )
    task_id = create.json()["task_id"]

    resp = client.get(f"/api/diagnosis/{task_id}/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == task_id
    assert body["status"] in ("pending", "crawling", "querying_llm", "completed", "failed")


def test_get_status_404_for_missing(client: TestClient) -> None:
    resp = client.get("/api/diagnosis/00000000-0000-0000-0000-000000000000/status")
    assert resp.status_code == 404


def test_list_reports_returns_array(client: TestClient) -> None:
    resp = client.get("/api/reports")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
```

Add fixture to `tests/conftest.py`:

```python
@pytest.fixture
def client(temp_db, monkeypatch) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with isolated test DB."""
    from fastapi.testclient import TestClient
    from app.core.config import get_settings
    from app.main import create_app

    # Override DB URL before app creates engine
    monkeypatch.setenv("DATABASE_URL", temp_db)
    get_settings.cache_clear()  # type: ignore[attr-defined]

    app = create_app()
    with TestClient(app) as c:
        yield c
```

You'll also need to import `Generator` at the top of `conftest.py`:

```python
from collections.abc import AsyncGenerator, Generator
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api.py -v
```

Expected: FAIL with `ModuleNotFoundError` or app not built yet.

- [ ] **Step 4: Refactor `app/main.py` to factory pattern**

Replace `D:/GEO2/backend/app/main.py` with:

```python
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
```

- [ ] **Step 5: Create `app/api/diagnosis.py`**

Create `D:/GEO2/backend/app/api/diagnosis.py`:

```python
"""Diagnosis task API: submit + status polling."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_factory
from app.models.schemas import DiagnosisRequest, DiagnosisTask
from app.repositories.report_repo import ReportRepository

router = APIRouter(tags=["diagnosis"])


async def get_session() -> AsyncSession:
    """Yield a DB session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


@router.post("/diagnosis", status_code=202, response_model=dict)
async def submit_diagnosis(
    request: DiagnosisRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Create a new diagnosis task. Returns task_id (UUID)."""
    repo = ReportRepository(session)
    row = await repo.create(request)
    # Note: actual pipeline execution is wired up in Task 8.1 (async worker)
    return {"task_id": row.id, "status": row.status}


@router.get("/diagnosis/{task_id}/status", response_model=DiagnosisTask)
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> DiagnosisTask:
    """Poll task status. Returns 404 if task_id unknown."""
    repo = ReportRepository(session)
    row = await repo.get_by_task_id(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")

    # Reconstruct DiagnosisTask from DB row
    from app.models.schemas import DiagnosisRequest as Req

    return DiagnosisTask(
        id=row.id,
        request=Req.model_validate_json(row.request_json),
        status=row.status,  # type: ignore[arg-type]
        progress=row.progress,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
```

- [ ] **Step 6: Create `app/api/reports.py`**

Create `D:/GEO2/backend/app/api/reports.py`:

```python
"""Report retrieval API."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.repositories.report_repo import ReportRepository
from app.services.report_service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=list[dict[str, Any]])
async def list_reports(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List recent reports (summaries)."""
    repo = ReportRepository(session)
    svc = ReportService(repo)
    return await svc.list_summaries(limit=50)


@router.get("/reports/{task_id}", response_model=dict)
async def get_report(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get full report JSON by task_id."""
    repo = ReportRepository(session)
    svc = ReportService(repo)
    report = await svc.get_report(task_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found or not completed")
    return report.model_dump()


@router.get("/reports/{task_id}/pdf")
async def get_report_pdf(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download report as PDF. Renders on first request."""
    repo = ReportRepository(session)
    svc = ReportService(repo)
    try:
        pdf_path = await svc.get_or_render_pdf(task_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="report not found or not completed")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"geo-report-{task_id[:8]}.pdf",
    )
```

- [ ] **Step 7: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 8: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): REST API for diagnosis + reports + PDF download + tests"
```

---

## Phase 8: Async Worker

### Task 8.1: Background Worker with asyncio Lock

**Files:**
- Create: `D:/GEO2/backend/app/tasks/__init__.py`
- Create: `D:/GEO2/backend/app/tasks/worker.py`
- Modify: `D:/GEO2/backend/app/api/diagnosis.py` (trigger worker on submit)

**Interfaces:**
- Consumes: DiagnosisService, ReportRepository
- Produces:
  - `submit_diagnosis(task_id, request)` — schedules background execution
  - Internal asyncio.Lock ensures single-flight execution

- [ ] **Step 1: Create `tasks/__init__.py`**

Create empty `D:/GEO2/backend/app/tasks/__init__.py`.

- [ ] **Step 2: Create `app/tasks/worker.py`**

Create `D:/GEO2/backend/app/tasks/worker.py`:

```python
"""Async background worker for executing diagnosis tasks."""
from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.domain.crawler import Crawler
from app.domain.llm_client import LLMClient
from app.models.schemas import DiagnosisRequest
from app.repositories.report_repo import ReportRepository
from app.services.diagnosis_service import DiagnosisService

logger = structlog.get_logger()

# Single global lock — MVP allows only one diagnosis at a time
_EXEC_LOCK = asyncio.Lock()


async def execute_diagnosis(task_id: str, request: DiagnosisRequest) -> None:
    """Run one diagnosis in the background.

    Acquires a global lock so only one runs at a time. Other tasks
    submitted while one is running remain in 'pending' state and will
    be picked up after the lock is released.
    """
    async with _EXEC_LOCK:
        logger.info("diagnosis_starting", task_id=task_id)
        await _run_one(task_id, request)


async def _run_one(task_id: str, request: DiagnosisRequest) -> None:
    """Execute the pipeline for one task."""
    from app.core.db import get_session_factory

    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        repo = ReportRepository(session)
        crawler = Crawler(settings)
        llm = LLMClient(settings)
        try:
            svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)
            await svc.run(task_id, request)
        finally:
            await crawler.close()


def schedule_diagnosis(task_id: str, request: DiagnosisRequest) -> asyncio.Task[None]:
    """Fire-and-forget background execution. Returns the asyncio.Task."""
    return asyncio.create_task(execute_diagnosis(task_id, request))
```

- [ ] **Step 3: Wire submit endpoint to trigger worker**

Modify `D:/GEO2/backend/app/api/diagnosis.py`. Update the `submit_diagnosis` function:

Replace the body of `submit_diagnosis` (after `repo.create(request)` line) with:

```python
    repo = ReportRepository(session)
    row = await repo.create(request)

    # Fire background worker (don't await)
    from app.tasks.worker import schedule_diagnosis
    schedule_diagnosis(row.id, request)

    return {"task_id": row.id, "status": row.status}
```

The full updated function:

```python
@router.post("/diagnosis", status_code=202, response_model=dict)
async def submit_diagnosis(
    request: DiagnosisRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Create a new diagnosis task. Returns task_id (UUID)."""
    from app.tasks.worker import schedule_diagnosis

    repo = ReportRepository(session)
    row = await repo.create(request)

    # Fire background worker (don't await)
    schedule_diagnosis(row.id, request)

    return {"task_id": row.id, "status": row.status}
```

- [ ] **Step 4: Add integration test for async worker**

Append to `tests/test_api.py`:

```python
def test_submit_starts_background_task(client: TestClient) -> None:
    """Submitting kicks off async work; status changes over time."""
    import time
    from unittest.mock import patch, AsyncMock

    # Patch the worker to avoid real network calls
    with patch("app.api.diagnosis.schedule_diagnosis") as mock_schedule:
        resp = client.post(
            "/api/diagnosis",
            json={
                "brand_name": "Async", "industry": "X",
                "official_url": "https://example.com",
                "target_questions": ["a", "b", "c"],
            },
        )
        assert resp.status_code == 202
        assert mock_schedule.called
```

- [ ] **Step 5: Run all tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend): async background worker with single-flight lock + tests"
```

---

## Phase 9: Frontend

### Task 9.1: API Client + TypeScript Types

**Files:**
- Create: `D:/GEO2/frontend/src/types/diagnosis.ts`
- Create: `D:/GEO2/frontend/src/api/client.ts`
- Create: `D:/GEO2/frontend/src/lib/utils.ts`

**Interfaces:**
- Consumes: backend REST API
- Produces:
  - Typed `api` object with methods: `submitDiagnosis`, `getStatus`, `getReport`, `listReports`, `getPdfUrl`

- [ ] **Step 1: Create `types/diagnosis.ts`**

Create `D:/GEO2/frontend/src/types/diagnosis.ts`:

```typescript
export type TaskStatus =
  | 'pending'
  | 'crawling'
  | 'querying_llm'
  | 'scoring'
  | 'rendering'
  | 'completed'
  | 'failed';

export interface DiagnosisRequest {
  brand_name: string;
  industry: string;
  official_url: string;
  target_questions: string[];
  competitors?: string[];
  contact_email?: string;
}

export interface DiagnosisTask {
  id: string;
  request: DiagnosisRequest;
  status: TaskStatus;
  progress: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface MentionResult {
  question: string;
  llm_provider: string;
  llm_answer: string;
  brand_mentioned: boolean;
  mention_position: number | null;
  competitors_mentioned: string[];
  sentiment: 'positive' | 'neutral' | 'negative';
  error: string | null;
}

export interface DimensionScore {
  name: string;
  score: number;
  weight: number;
  evidence: string[];
}

export interface ScoreCard {
  authority: DimensionScore;
  relevance: DimensionScore;
  structure: DimensionScore;
  freshness: DimensionScore;
  verifiability: DimensionScore;
  overall: number;
  mention_rate: number;
  avg_mention_position: number | null;
}

export interface Suggestion {
  priority: 'P0' | 'P1' | 'P2';
  category: string;
  title: string;
  detail: string;
  action_steps: string[];
  expected_impact: string;
}

export interface BrandInfo {
  name: string;
  industry: string;
  official_url: string;
}

export interface SiteAudit {
  url: string;
  crawl_status: 'success' | 'partial' | 'failed';
  crawled_at: string;
  schema: Record<string, unknown>;
  eeat: Record<string, unknown>;
  structure: Record<string, unknown>;
  freshness: Record<string, unknown>;
  page_load_ms: number | null;
  robots_txt_allows_ai_bots: Record<string, boolean>;
}

export interface Report {
  id: string;
  task_id: string;
  brand: BrandInfo;
  site_audit: SiteAudit | null;
  mentions: MentionResult[];
  score_card: ScoreCard;
  suggestions: Suggestion[];
  summary: string;
  created_at: string;
  pdf_available: boolean;
}

export interface ReportSummary {
  id: string;
  brand_name: string;
  industry: string;
  status: TaskStatus;
  created_at: string;
  overall_score: number | null;
}
```

- [ ] **Step 2: Create `lib/utils.ts`**

Create `D:/GEO2/frontend/src/lib/utils.ts`:

```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN');
}

export function scoreColor(score: number): string {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-blue-600';
  if (score >= 40) return 'text-yellow-600';
  return 'text-red-600';
}
```

- [ ] **Step 3: Create `api/client.ts`**

Create `D:/GEO2/frontend/src/api/client.ts`:

```typescript
import type {
  DiagnosisRequest,
  DiagnosisTask,
  Report,
  ReportSummary,
} from '@/types/diagnosis';

const BASE = '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new ApiError(resp.status, body || resp.statusText);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  submitDiagnosis(req: DiagnosisRequest): Promise<{ task_id: string; status: string }> {
    return request('/diagnosis', { method: 'POST', body: JSON.stringify(req) });
  },

  getStatus(taskId: string): Promise<DiagnosisTask> {
    return request(`/diagnosis/${taskId}/status`);
  },

  getReport(taskId: string): Promise<Report> {
    return request(`/reports/${taskId}`);
  },

  listReports(): Promise<ReportSummary[]> {
    return request('/reports');
  },

  getPdfUrl(taskId: string): string {
    return `${BASE}/reports/${taskId}/pdf`;
  },
};

export { ApiError };
```

- [ ] **Step 4: Verify type-check passes**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend): API client + TypeScript types matching backend schemas"
```

---

### Task 9.2: Multi-Step Wizard Form

**Files:**
- Create: `D:/GEO2/frontend/src/components/WizardShell.tsx`
- Create: `D:/GEO2/frontend/src/components/WizardStep.tsx`
- Create: `D:/GEO2/frontend/src/pages/NewDiagnosis.tsx`
- Modify: `D:/GEO2/frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create `WizardShell.tsx`**

Create `D:/GEO2/frontend/src/components/WizardShell.tsx`:

```tsx
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface WizardShellProps {
  currentStep: number;
  totalSteps: number;
  stepTitles: string[];
  children: ReactNode;
}

export function WizardShell({ currentStep, totalSteps, stepTitles, children }: WizardShellProps) {
  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">GEO 诊断</h1>
        <p className="text-gray-600 mb-6">输入品牌信息，60-90 秒获取诊断报告</p>

        {/* Step indicator */}
        <div className="flex items-center mb-8">
          {stepTitles.map((title, idx) => (
            <div key={title} className="flex items-center flex-1 last:flex-none">
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium',
                  idx < currentStep && 'bg-green-500 text-white',
                  idx === currentStep && 'bg-blue-600 text-white',
                  idx > currentStep && 'bg-gray-200 text-gray-500',
                )}
              >
                {idx < currentStep ? '✓' : idx + 1}
              </div>
              <div className={cn('ml-2 text-sm', idx === currentStep ? 'font-medium' : 'text-gray-500')}>
                {title}
              </div>
              {idx < totalSteps - 1 && (
                <div className={cn('flex-1 h-px mx-3', idx < currentStep ? 'bg-green-500' : 'bg-gray-200')} />
              )}
            </div>
          ))}
        </div>

        <div className="bg-white rounded-lg shadow p-6">{children}</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `WizardStep.tsx`**

Create `D:/GEO2/frontend/src/components/WizardStep.tsx`:

```tsx
import type { ReactNode } from 'react';

interface WizardStepProps {
  title: string;
  description?: string;
  children: ReactNode;
  onBack?: () => void;
  onNext?: () => void;
  nextDisabled?: boolean;
  nextLabel?: string;
  isLastStep?: boolean;
}

export function WizardStep({
  title,
  description,
  children,
  onBack,
  onNext,
  nextDisabled,
  nextLabel = '下一步',
  isLastStep,
}: WizardStepProps) {
  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">{title}</h2>
      {description && <p className="text-gray-600 mb-6">{description}</p>}
      <div className="mb-6">{children}</div>
      <div className="flex justify-between">
        <button
          type="button"
          onClick={onBack}
          disabled={!onBack}
          className="px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-30"
        >
          ← 上一步
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={nextDisabled}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
        >
          {isLastStep ? '提交诊断' : `${nextLabel} →`}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `pages/NewDiagnosis.tsx`**

Create `D:/GEO2/frontend/src/pages/NewDiagnosis.tsx`:

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';

import { WizardShell } from '@/components/WizardShell';
import { WizardStep } from '@/components/WizardStep';
import { api } from '@/api/client';
import type { DiagnosisRequest } from '@/types/diagnosis';

const STEP_TITLES = ['品牌信息', '目标问题', '确认提交'];

export default function NewDiagnosis() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<DiagnosisRequest>({
    brand_name: '',
    industry: '',
    official_url: '',
    target_questions: ['', '', ''],
    competitors: [],
    contact_email: '',
  });

  const submit = useMutation({
    mutationFn: (req: DiagnosisRequest) => api.submitDiagnosis(req),
    onSuccess: (data) => {
      navigate(`/diagnosis/${data.task_id}/status`);
    },
  });

  const update = <K extends keyof DiagnosisRequest>(key: K, value: DiagnosisRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const updateQuestion = (idx: number, value: string) => {
    const next = [...form.target_questions];
    next[idx] = value;
    update('target_questions', next);
  };

  const canNextFromStep1 =
    form.brand_name.trim().length >= 1 &&
    form.industry.trim().length >= 1 &&
    /^https?:\/\/.+/.test(form.official_url);

  const canNextFromStep2 = form.target_questions.filter((q) => q.trim().length >= 5).length >= 3;

  return (
    <WizardShell currentStep={step} totalSteps={STEP_TITLES.length} stepTitles={STEP_TITLES}>
      {step === 0 && (
        <WizardStep
          title="品牌信息"
          description="告诉我们您要诊断的品牌"
          onNext={() => setStep(1)}
          nextDisabled={!canNextFromStep1}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">品牌名 *</label>
              <input
                type="text"
                value={form.brand_name}
                onChange={(e) => update('brand_name', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="如：小米"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">行业 *</label>
              <input
                type="text"
                value={form.industry}
                onChange={(e) => update('industry', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="如：消费电子"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">官网 URL *</label>
              <input
                type="url"
                value={form.official_url}
                onChange={(e) => update('official_url', e.target.value)}
                className="w-full px-3 py-2 border rounded-md"
                placeholder="https://www.example.com"
              />
            </div>
          </div>
        </WizardStep>
      )}

      {step === 1 && (
        <WizardStep
          title="目标问题"
          description="用户最常问的 3-5 个问题（AI 会基于这些问题测试提及率）"
          onBack={() => setStep(0)}
          onNext={() => setStep(2)}
          nextDisabled={!canNextFromStep2}
        >
          <div className="space-y-3">
            {form.target_questions.map((q, idx) => (
              <div key={idx}>
                <label className="block text-sm font-medium mb-1">问题 {idx + 1}</label>
                <input
                  type="text"
                  value={q}
                  onChange={(e) => updateQuestion(idx, e.target.value)}
                  className="w-full px-3 py-2 border rounded-md"
                  placeholder={`如：${idx === 0 ? 'XX 品牌怎么样' : idx === 1 ? 'XX 值得买吗' : 'XX vs 竞品'}`}
                />
              </div>
            ))}
          </div>
        </WizardStep>
      )}

      {step === 2 && (
        <WizardStep
          title="确认提交"
          description="检查信息无误后开始诊断"
          onBack={() => setStep(1)}
          onNext={() => submit.mutate(form)}
          nextDisabled={submit.isPending}
          isLastStep
        >
          <div className="bg-gray-50 p-4 rounded-md space-y-2 text-sm">
            <div><strong>品牌：</strong>{form.brand_name} ({form.industry})</div>
            <div><strong>官网：</strong>{form.official_url}</div>
            <div><strong>目标问题：</strong>
              <ul className="list-disc list-inside mt-1">
                {form.target_questions.filter((q) => q.trim()).map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          </div>
          {submit.isError && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
              提交失败：{String(submit.error)}
            </div>
          )}
        </WizardStep>
      )}
    </WizardShell>
  );
}
```

- [ ] **Step 4: Verify type-check**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend): multi-step wizard form for diagnosis submission"
```

---

### Task 9.3: Status Page with Polling

**Files:**
- Create: `D:/GEO2/frontend/src/pages/DiagnosisStatus.tsx`
- Modify: `D:/GEO2/frontend/src/App.tsx`

- [ ] **Step 1: Create `DiagnosisStatus.tsx`**

Create `D:/GEO2/frontend/src/pages/DiagnosisStatus.tsx`:

```tsx
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';

const STATUS_LABELS: Record<string, string> = {
  pending: '等待开始',
  crawling: '正在抓取官网',
  querying_llm: '正在向 AI 提问',
  scoring: '正在评分',
  rendering: '正在生成报告',
  completed: '完成',
  failed: '失败',
};

export default function DiagnosisStatus() {
  const { taskId = '' } = useParams<{ taskId: string }>();
  const navigate = useNavigate();

  const { data: task, error } = useQuery({
    queryKey: ['task-status', taskId],
    queryFn: () => api.getStatus(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'completed' || status === 'failed') return false;
      return 1500;
    },
  });

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg">
          <h2 className="text-red-700 font-medium">加载失败</h2>
          <p className="text-red-600 text-sm mt-1">{String(error)}</p>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        加载中...
      </div>
    );
  }

  if (task.status === 'completed') {
    setTimeout(() => navigate(`/reports/${taskId}`), 0);
    return <div className="min-h-screen flex items-center justify-center">跳转中...</div>;
  }

  if (task.status === 'failed') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-red-50 p-6 rounded-lg max-w-md">
          <h2 className="text-red-700 font-medium text-lg">诊断失败</h2>
          <p className="text-red-600 mt-2">{task.error_message}</p>
          <button
            type="button"
            onClick={() => navigate('/new')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md"
          >
            重新诊断
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-lg shadow-md max-w-md w-full">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          {STATUS_LABELS[task.status] ?? '处理中...'}
        </h1>
        <p className="text-gray-600 mb-6">
          品牌：<strong>{task.request.brand_name}</strong>
        </p>

        {/* Progress bar */}
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden mb-2">
          <div
            className="bg-blue-600 h-full transition-all duration-500"
            style={{ width: `${task.progress}%` }}
          />
        </div>
        <p className="text-sm text-gray-500 text-right">{task.progress}%</p>

        {/* Stage indicators */}
        <div className="mt-6 space-y-2">
          {['crawling', 'querying_llm', 'scoring', 'rendering'].map((stage, idx) => {
            const stageOrder = ['pending', 'crawling', 'querying_llm', 'scoring', 'rendering', 'completed'];
            const currentIdx = stageOrder.indexOf(task.status);
            const stageIdx = stageOrder.indexOf(stage);
            const isDone = currentIdx > stageIdx;
            const isCurrent = currentIdx === stageIdx;
            return (
              <div key={stage} className="flex items-center text-sm">
                <div
                  className={`w-5 h-5 rounded-full mr-2 flex items-center justify-center text-xs ${
                    isDone ? 'bg-green-500 text-white' : isCurrent ? 'bg-blue-500 text-white' : 'bg-gray-200'
                  }`}
                >
                  {isDone ? '✓' : isCurrent ? '●' : ''}
                </div>
                <span className={isCurrent ? 'font-medium' : 'text-gray-500'}>
                  {STATUS_LABELS[stage]}
                </span>
              </div>
            );
          })}
        </div>

        <p className="mt-6 text-xs text-gray-400 text-center">
          通常需要 60-90 秒。请勿关闭页面。
        </p>
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
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend): diagnosis status page with polling + stage indicators"
```

---

### Task 9.4: Report View Page with Radar Chart

**Files:**
- Create: `D:/GEO2/frontend/src/components/ScoreRadarChart.tsx`
- Create: `D:/GEO2/frontend/src/components/SuggestionCard.tsx`
- Create: `D:/GEO2/frontend/src/pages/ReportView.tsx`
- Modify: `D:/GEO2/frontend/src/App.tsx`

- [ ] **Step 1: Create `ScoreRadarChart.tsx`**

Create `D:/GEO2/frontend/src/components/ScoreRadarChart.tsx`:

```tsx
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts';

import type { ScoreCard } from '@/types/diagnosis';

interface Props {
  scoreCard: ScoreCard;
}

export function ScoreRadarChart({ scoreCard }: Props) {
  const data = [
    { dim: scoreCard.authority.name, score: scoreCard.authority.score },
    { dim: scoreCard.relevance.name, score: scoreCard.relevance.score },
    { dim: scoreCard.structure.name, score: scoreCard.structure.score },
    { dim: scoreCard.freshness.name, score: scoreCard.freshness.score },
    { dim: scoreCard.verifiability.name, score: scoreCard.verifiability.score },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data}>
        <PolarGrid />
        <PolarAngleAxis dataKey="dim" />
        <PolarRadiusAxis angle={90} domain={[0, 10]} />
        <Radar name="评分" dataKey="score" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Create `SuggestionCard.tsx`**

Create `D:/GEO2/frontend/src/components/SuggestionCard.tsx`:

```tsx
import type { Suggestion } from '@/types/diagnosis';

import { cn } from '@/lib/utils';

interface Props {
  suggestion: Suggestion;
}

const PRIORITY_STYLES: Record<string, string> = {
  P0: 'border-l-red-500 bg-red-50',
  P1: 'border-l-yellow-500 bg-yellow-50',
  P2: 'border-l-green-500 bg-green-50',
};

const PRIORITY_LABEL: Record<string, string> = {
  P0: '紧急',
  P1: '重要',
  P2: '建议',
};

export function SuggestionCard({ suggestion }: Props) {
  return (
    <div className={cn('border-l-4 rounded-md p-4 mb-3', PRIORITY_STYLES[suggestion.priority])}>
      <div className="flex items-start justify-between mb-2">
        <h4 className="font-semibold text-gray-900">{suggestion.title}</h4>
        <span className="text-xs px-2 py-1 rounded bg-white border">
          [{suggestion.priority}] {PRIORITY_LABEL[suggestion.priority]}
        </span>
      </div>
      <p className="text-sm text-gray-700 mb-3">{suggestion.detail}</p>
      {suggestion.action_steps.length > 0 && (
        <div className="text-sm">
          <strong className="text-gray-900">行动步骤：</strong>
          <ol className="list-decimal list-inside mt-1 space-y-1 text-gray-700">
            {suggestion.action_steps.map((step, idx) => (
              <li key={idx}>{step}</li>
            ))}
          </ol>
        </div>
      )}
      <p className="text-xs text-gray-500 mt-3">
        <strong>预期效果：</strong>{suggestion.expected_impact}
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Create `ReportView.tsx`**

Create `D:/GEO2/frontend/src/pages/ReportView.tsx`:

```tsx
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { ScoreRadarChart } from '@/components/ScoreRadarChart';
import { SuggestionCard } from '@/components/SuggestionCard';
import { formatDate, scoreColor } from '@/lib/utils';

export default function ReportView() {
  const { reportId = '' } = useParams<{ reportId: string }>();

  const { data: report, error, isLoading } = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.getReport(reportId),
  });

  if (isLoading) {
    return <div className="p-8 text-center text-gray-500">加载报告中...</div>;
  }

  if (error || !report) {
    return (
      <div className="p-8">
        <div className="bg-red-50 p-4 rounded-md text-red-700">
          报告加载失败：{String(error)}
        </div>
        <Link to="/" className="text-blue-600 mt-4 inline-block">← 返回首页</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                {report.brand.name}
              </h1>
              <p className="text-gray-600">
                {report.brand.industry} · {report.brand.official_url}
              </p>
              <p className="text-sm text-gray-400 mt-1">
                {formatDate(report.created_at)}
              </p>
            </div>
            <a
              href={api.getPdfUrl(report.id)}
              download
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              下载 PDF
            </a>
          </div>
        </div>

        {/* Overall score */}
        <div className="bg-white rounded-lg shadow p-6 mb-6 text-center">
          <p className="text-gray-500 mb-2">综合 GEO 评分</p>
          <div className={`text-6xl font-bold ${scoreColor(report.score_card.overall)}`}>
            {report.score_card.overall.toFixed(1)}
            <span className="text-2xl text-gray-400">/100</span>
          </div>
        </div>

        {/* Summary */}
        <div className="bg-blue-50 border-l-4 border-blue-500 rounded-md p-4 mb-6">
          <h3 className="font-semibold text-blue-900 mb-2">执行摘要</h3>
          <p className="text-blue-800">{report.summary}</p>
        </div>

        {/* Radar chart */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">五维度评分</h2>
          <ScoreRadarChart scoreCard={report.score_card} />

          {/* Dimension details */}
          <div className="mt-6 space-y-3">
            {([
              ['authority', report.score_card.authority],
              ['relevance', report.score_card.relevance],
              ['structure', report.score_card.structure],
              ['freshness', report.score_card.freshness],
              ['verifiability', report.score_card.verifiability],
            ] as const).map(([key, dim]) => (
              <div key={key} className="border-l-4 border-blue-500 pl-4">
                <div className="flex justify-between items-baseline">
                  <strong className="text-gray-900">{dim.name}</strong>
                  <span className={`text-lg font-bold ${scoreColor(dim.score * 10)}`}>
                    {dim.score.toFixed(1)}/10
                  </span>
                </div>
                {dim.evidence.length > 0 && (
                  <ul className="text-sm text-gray-600 mt-1 space-y-1">
                    {dim.evidence.map((ev, i) => (
                      <li key={i}>• {ev}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Mentions */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">
            AI 提及率（{(report.score_card.mention_rate * 100).toFixed(0)}%）
          </h2>
          <div className="space-y-2">
            {report.mentions.map((m, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-md ${
                  m.brand_mentioned ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border'
                }`}
              >
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{m.question}</span>
                  <span className="text-gray-500">
                    {m.llm_provider} · {m.brand_mentioned ? `✓ 位置 ${m.mention_position}` : '✗'}
                    {m.error && ' (错误)'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Suggestions */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">
            优化建议（{report.suggestions.length} 条）
          </h2>
          {report.suggestions.map((s, idx) => (
            <SuggestionCard key={idx} suggestion={s} />
          ))}
        </div>

        <div className="mt-8 text-center">
          <Link to="/" className="text-blue-600 hover:underline">
            ← 返回报告列表
          </Link>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend): report view page with radar chart + suggestions"
```

---

### Task 9.5: Report List Page

**Files:**
- Create: `D:/GEO2/frontend/src/pages/ReportList.tsx`

- [ ] **Step 1: Create `ReportList.tsx`**

Create `D:/GEO2/frontend/src/pages/ReportList.tsx`:

```tsx
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate, scoreColor } from '@/lib/utils';

export default function ReportList() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => api.listReports(),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">历史报告</h1>
          <Link
            to="/new"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            + 新建诊断
          </Link>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {reports && reports.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有诊断报告。<Link to="/new" className="text-blue-600">立即创建</Link>
          </div>
        )}

        {reports && reports.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {reports.map((r) => (
              <Link
                key={r.id}
                to={`/reports/${r.id}`}
                className="block p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-medium text-gray-900">{r.brand_name}</div>
                    <div className="text-sm text-gray-500">
                      {r.industry} · {formatDate(r.created_at)}
                    </div>
                  </div>
                  <div className="text-right">
                    {r.overall_score != null ? (
                      <div className={`text-2xl font-bold ${scoreColor(r.overall_score)}`}>
                        {r.overall_score.toFixed(0)}
                      </div>
                    ) : (
                      <div className="text-sm text-gray-400">{r.status}</div>
                    )}
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
```

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend): report list page"
```

---

### Task 9.6: App Shell + Routing

**Files:**
- Replace: `D:/GEO2/frontend/src/App.tsx`

- [ ] **Step 1: Replace `App.tsx` with full router**

Replace `D:/GEO2/frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Route, Routes, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import NewDiagnosis from '@/pages/NewDiagnosis';
import DiagnosisStatus from '@/pages/DiagnosisStatus';
import ReportView from '@/pages/ReportView';
import ReportList from '@/pages/ReportList';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function Header() {
  return (
    <header className="bg-white border-b">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link to="/" className="text-xl font-bold text-gray-900">
          GEO 诊断 Agent
        </Link>
        <nav className="space-x-4">
          <Link to="/" className="text-gray-600 hover:text-gray-900">历史</Link>
          <Link to="/new" className="px-3 py-1 bg-blue-600 text-white rounded-md">
            新建诊断
          </Link>
        </nav>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Header />
        <Routes>
          <Route path="/" element={<ReportList />} />
          <Route path="/new" element={<NewDiagnosis />} />
          <Route path="/diagnosis/:taskId/status" element={<DiagnosisStatus />} />
          <Route path="/reports/:reportId" element={<ReportView />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 2: Verify dev server boots**

```bash
cd "D:/GEO2/frontend" && npm run dev &
sleep 5
curl http://localhost:5173/ | head -20
kill %1 2>/dev/null || true
```

Expected: HTML response including "GEO 诊断 Agent".

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/App.tsx && git commit -m "feat(frontend): app shell with routing + React Query provider"
```

---

## Phase 10: End-to-End Verification & Documentation

### Task 10.1: End-to-End Backend Integration Test

**Files:**
- Modify: `D:/GEO2/backend/tests/test_api.py` (add E2E with mocked workers)

- [ ] **Step 1: Append E2E test**

Append to `tests/test_api.py`:

```python
def test_full_diagnosis_flow_with_mocked_workers(client: TestClient) -> None:
    """Submit → poll → complete → fetch report → download PDF (mocked)."""
    from unittest.mock import patch, AsyncMock
    from datetime import datetime, timezone

    # Mock schedule_diagnosis to run inline
    async def inline_run(task_id, request):
        from app.core.db import get_session_factory
        from app.repositories.report_repo import ReportRepository
        from app.models.schemas import SiteAudit, SchemaCoverage, ScoreCard, DimensionScore
        from app.domain.scorer import compute_score_card, generate_suggestions

        factory = get_session_factory()
        async with factory() as session:
            repo = ReportRepository(session)
            audit = SiteAudit(
                url=str(request.official_url), crawl_status="success",
                crawled_at=datetime.now(timezone.utc),
                schema=SchemaCoverage(has_organization=True, detected_schemas=["Organization"]),
            )
            mentions = []
            card = compute_score_card(audit, mentions)
            suggestions = generate_suggestions(card, audit, mentions)
            report = {
                "id": task_id, "task_id": task_id,
                "brand": {"name": request.brand_name, "industry": request.industry,
                          "official_url": str(request.official_url)},
                "site_audit": audit.model_dump(mode="json"),
                "mentions": [], "score_card": card.model_dump(),
                "suggestions": [s.model_dump() for s in suggestions],
                "summary": "测试摘要",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pdf_available": False,
            }
            import json
            await repo.update_report(task_id, json.dumps(report, default=str))
            await repo.update_status(task_id, status="completed", progress=100)

    with patch("app.api.diagnosis.schedule_diagnosis") as mock:
        mock.side_effect = lambda tid, req: AsyncMock(return_value=inline_run(tid, req))()

        # 1. Submit
        resp = client.post("/api/diagnosis", json={
            "brand_name": "E2E测试", "industry": "测试",
            "official_url": "https://example.com",
            "target_questions": ["q1", "q2", "q3"],
        })
        assert resp.status_code == 202
        task_id = resp.json()["task_id"]

        # 2. Poll status until completed (or timeout)
        import time
        for _ in range(20):
            status_resp = client.get(f"/api/diagnosis/{task_id}/status")
            assert status_resp.status_code == 200
            if status_resp.json()["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        assert status_resp.json()["status"] == "completed"

        # 3. Get full report
        report_resp = client.get(f"/api/reports/{task_id}")
        assert report_resp.status_code == 200
        report = report_resp.json()
        assert report["brand"]["name"] == "E2E测试"
        assert "score_card" in report

        # 4. List reports
        list_resp = client.get("/api/reports")
        assert list_resp.status_code == 200
        assert any(r["id"] == task_id for r in list_resp.json())

        # 5. PDF download
        with patch("app.services.report_service.render_pdf") as mock_render:
            from pathlib import Path
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4\n%fake pdf content")
                pdf_path = f.name
            mock_render.return_value = pdf_path

            pdf_resp = client.get(f"/api/reports/{task_id}/pdf")
            assert pdf_resp.status_code == 200
            assert pdf_resp.headers["content-type"] == "application/pdf"
            os.unlink(pdf_path)
```

- [ ] **Step 2: Run all backend tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v --tb=short
```

Expected: All tests PASS (unit + integration + E2E).

- [ ] **Step 3: Verify coverage**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest --cov=app --cov-report=term-missing
```

Expected: Overall coverage ≥ 70%; `app/domain/scorer.py` coverage ≥ 90%.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add backend/tests/ && git commit -m "test(backend): end-to-end diagnosis flow integration test"
```

---

### Task 10.2: Frontend E2E with Playwright (Smoke Test)

**Files:**
- Create: `D:/GEO2/frontend/playwright.config.ts`
- Create: `D:/GEO2/frontend/tests/e2e/diagnosis-flow.spec.ts`
- Modify: `D:/GEO2/frontend/package.json` (add scripts)

**Scope:** MVP E2E is a smoke test only — verifies the UI loads, form submits, status page renders. We **do not** depend on a real LLM API; the test runs against a backend with stubbed workers.

- [ ] **Step 1: Install Playwright**

```bash
cd "D:/GEO2/frontend" && npm install -D @playwright/test && npx playwright install --with-deps chromium
```

- [ ] **Step 2: Create `playwright.config.ts`**

Create `D:/GEO2/frontend/playwright.config.ts`:

```typescript
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
  },
});
```

- [ ] **Step 3: Create smoke test**

Create `D:/GEO2/frontend/tests/e2e/diagnosis-flow.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test('home page loads and shows empty state or list', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('GEO 诊断 Agent')).toBeVisible();
  await expect(page.getByRole('link', { name: /新建诊断/ })).toBeVisible();
});

test('new diagnosis form has 3 steps', async ({ page }) => {
  await page.goto('/new');
  await expect(page.getByText('品牌信息')).toBeVisible();
  await expect(page.getByLabel(/品牌名/)).toBeVisible();
});

test('form validates required fields', async ({ page }) => {
  await page.goto('/new');
  // Click next without filling
  await page.getByRole('button', { name: /下一步/ }).click();
  // Should still be on step 0 because next is disabled
  await expect(page.getByText('品牌信息')).toBeVisible();
});
```

- [ ] **Step 4: Add scripts to `package.json`**

In `frontend/package.json` `scripts`, add:

```json
    "test:e2e": "playwright test"
```

- [ ] **Step 5: Run E2E (requires both backend + frontend running)**

```bash
cd "D:/GEO2" && docker-compose up -d
sleep 30
cd "D:/GEO2/frontend" && npm run test:e2e
cd "D:/GEO2" && docker-compose down
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add frontend/playwright.config.ts frontend/tests/ frontend/package.json && git commit -m "test(frontend): Playwright E2E smoke tests for main UI flows"
```

---

### Task 10.3: Manual Verification Checklist

This task has no code. It documents the 4-scenario checklist that **must** be run before declaring v0.1 "done".

**Files:**
- Create: `D:/GEO2/docs/MANUAL_VERIFICATION.md`

- [ ] **Step 1: Write the checklist doc**

Create `D:/GEO2/docs/MANUAL_VERIFICATION.md`:

```markdown
# 手动验证清单 — GEO Agent v0.1

发布前必跑 4 个场景，全部通过才能认为 MVP v0.1 "完成"。

## 前置条件

\`\`\`bash
cd "D:/GEO2"
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
docker-compose up --build -d
sleep 30  # 等待服务启动
\`\`\`

## 场景 1: 完整诊断流程 ✅

1. 浏览器打开 http://localhost:5173
2. 点击 "新建诊断"
3. 步骤 1 填：
   - 品牌名: "小米"
   - 行业: "消费电子"
   - 官网: "https://www.mi.com"
4. 步骤 2 填 3 个问题：
   - "小米手机怎么样"
   - "小米14值得买吗"
   - "小米 vs 华为"
5. 步骤 3 点 "提交诊断"

**预期**：
- 进度页出现，显示阶段切换（crawling → querying_llm → scoring → completed）
- 90 秒内跳转到报告页
- 报告页显示：综合分数、雷达图、≥3 条建议
- 点 "下载 PDF" 下载到有效 PDF 文件，中文不乱码

## 场景 2: 网站无法访问 ❌

1. 步骤 1 填官网: "https://this-domain-does-not-exist-xyz123.com"
2. 提交

**预期**：
- 进度页显示 "诊断失败"
- 错误信息包含 "官网无法访问"

## 场景 3: LLM 部分失败 ⚠️

1. 编辑 .env，设置 `DEEPSEEK_API_KEY=sk-invalid-key`
2. `docker-compose restart backend`
3. 提交一个真实品牌的诊断

**预期**：
- 任务最终标记 failed 或 completed with mention_rate=N/A
- 网页报告能看到 LLM 错误信息（不阻断整个报告生成）
- mention_rate 标注 "N/A" 或显示 "0% (0/0)"

## 场景 4: PDF 下载与中文渲染 📄

承接场景 1 的报告：

1. 在报告页点 "下载 PDF"
2. 用 PDF 阅读器打开

**预期**：
- 文件名: `geo-report-<id 前 8 位>.pdf`
- 文件大小 > 10KB
- 中文显示正常（Noto Sans CJK 字体）
- 包含：标题、综合分、五维度、建议清单

## 通过标准

- [ ] 场景 1 通过
- [ ] 场景 2 通过
- [ ] 场景 3 通过
- [ ] 场景 4 通过

4 项全过才能标记 v0.1 完成。
\`\`\`

- [ ] **Step 2: Commit**

\`\`\`bash
cd "D:/GEO2" && git add docs/MANUAL_VERIFICATION.md && git commit -m "docs: manual verification checklist for v0.1"
\`\`\`

---

### Task 10.4: Final README and Deployment Documentation

**Files:**
- Replace: `D:/GEO2/README.md`

- [ ] **Step 1: Replace README with comprehensive version**

Replace `D:/GEO2/README.md`:

```markdown
# GEO 优化 Agent v0.1

白帽 GEO（生成引擎优化）诊断工具。输入品牌信息 → 自动生成 GEO 健康度诊断报告。

## 功能

- 一键诊断品牌的 GEO 健康度
- 5 个维度的评分卡（权威度、内容相关性、结构、更新频率、数据可验证性）
- AI 平台实测的提及率（DeepSeek / Kimi）
- 可执行的优化建议清单
- 网页报告 + PDF 下载

## 快速开始

### 前置条件

- Docker + docker-compose
- 一个 DeepSeek 或 Kimi 的 API key

### 启动

\`\`\`bash
git clone <repo>  # 或解压项目目录
cd GEO2
cp .env.example .env
# 编辑 .env，至少填入 DEEPSEEK_API_KEY
docker-compose up --build
\`\`\`

访问：
- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 开发

### 项目结构

\`\`\`
GEO2/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 入口
│   │   ├── api/             # REST 路由
│   │   ├── core/            # 配置 + DB
│   │   ├── domain/          # 业务逻辑（crawler, llm, scorer, renderer）
│   │   ├── models/          # Pydantic + SQLAlchemy
│   │   ├── repositories/    # DB 访问层
│   │   ├── services/        # 编排
│   │   ├── tasks/           # 异步 worker
│   │   └── templates/       # Jinja2 PDF 模板
│   └── tests/
├── frontend/                # React + Vite 前端
│   ├── src/
│   │   ├── pages/           # 路由页面
│   │   ├── components/      # 复用组件
│   │   ├── api/             # API 客户端
│   │   └── types/           # TypeScript 类型
│   └── tests/e2e/
├── docs/
│   ├── superpowers/
│   │   ├── specs/           # 设计文档
│   │   └── plans/           # 实施计划
│   └── MANUAL_VERIFICATION.md
├── docker-compose.yml
└── .env.example
\`\`\`

### 后端开发

\`\`\`bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
pytest -v  # 跑测试
\`\`\`

启动开发服务器：

\`\`\`bash
uvicorn app.main:app --reload --port 8000
\`\`\`

### 前端开发

\`\`\`bash
cd frontend
npm install
npm run dev  # 启动 dev server (端口 5173)
\`\`\`

类型检查：

\`\`\`bash
npm run lint
\`\`\`

E2E 测试：

\`\`\`bash
npm run test:e2e
\`\`\`

## 启用 Kimi 作为第二个 LLM

编辑 `.env`：

\`\`\`bash
KIMI_API_KEY=sk-your-kimi-key
LLM_PROVIDERS=deepseek,kimi
\`\`\`

重启后端：

\`\`\`bash
docker-compose restart backend
\`\`\`

## 文档

- 设计文档: [docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md](docs/superpowers/specs/2026-07-09-geo-optimization-agent-design.md)
- 实施计划: [docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md](docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md)
- 手动验证清单: [docs/MANUAL_VERIFICATION.md](docs/MANUAL_VERIFICATION.md)

## 合规说明

本工具**只做诊断和建议**，不做内容伪造、AI 投毒等黑帽 GEO 操作。所有建议基于公开方法论，不构成具体法律/财务/医疗建议。

详见设计文档 §9 合规与边界。

## 许可证

MIT（待定）
```

- [ ] **Step 2: Final commit**

\`\`\`bash
cd "D:/GEO2" && git add README.md && git commit -m "docs: comprehensive README with development setup and deployment"
\`\`\`

---

## Self-Review

After writing this plan, run the writing-plans self-review checklist:

**1. Spec coverage** — Every requirement in the spec is covered:
- Spec §1 (background, scope) → Phase 0 (scaffold) + README §合规说明
- Spec §2 (users, scenarios) → Task 9.2 (wizard) + Task 9.3 (status)
- Spec §3 (architecture) → Task 0.2-0.4 (monolith scaffold)
- Spec §4 (data models) → Task 1.2 (schemas), Task 1.3 (repo)
- Spec §5 (diagnosis flow) → Task 6.1 (DiagnosisService) + Task 8.1 (worker)
- Spec §6 (output combo) → Task 5.1 (renderer), Task 7 (PDF endpoint)
- Spec §7 (error handling) → Task 2.1 (exceptions), Task 6.1 (try/except)
- Spec §8 (testing) → Task 10.1-10.2 (E2E) + Task 10.3 (manual checklist)
- Spec §9 (compliance) → README + Task 6.1 (summary generation has no AI poisoning)
- Spec §10 (risks) → PDF font in Dockerfile (Task 0.4) + SPA detection (Task 3.4)

**2. Placeholder scan** — No TBD/TODO/"implement later". All code blocks complete.

**3. Type consistency** —
- `MentionResult.error` defined in Task 1.2 (schemas), used in Task 2.2 (LLM client), Task 4.1 (scorer filters by it) ✓
- `DiagnosisService(repo, crawler, llm, settings)` signature consistent across Task 6.1 + Task 8.1 ✓
- `ReportRepository.update_status(task_id, status, progress, error=None)` matches all callers ✓
- `Crawler.audit(url) -> SiteAudit` defined Task 3.4, consumed by Task 6.1 ✓
- `compute_score_card(audit, mentions) -> ScoreCard` defined Task 4.1, consumed by Task 6.1 ✓
- `render_pdf(report, output_path) -> str` defined Task 5.1, consumed by Task 6.2 ✓
- Frontend types in Task 9.1 mirror backend Pydantic schemas in Task 1.2 ✓

All consistent.

---

## Execution Handoff

This plan is **complete** and saved to:
`D:/GEO2/docs/superpowers/plans/2026-07-09-geo-optimization-agent-v0.1.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task with two-stage review between tasks. Best for catching issues early and maintaining quality across 25 tasks.

**2. Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints. Faster but no inter-task review.

**Which approach?**


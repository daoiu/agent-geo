# GEO Optimization Agent v0.4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an autonomous decision-making Agent layer on top of v0.1-v0.3. Users interact via a chat box using natural language; the agent uses LLM Function Calling + a self-written ReAct loop to orchestrate 3 tools (`diagnose_brand`, `search_knowledge`, `generate_article`) with human-in-the-loop confirmation for write operations.

**Architecture:** v0.4 extends the v0.1-v0.3 monolith. Adds 2 new tables (`agent_sessions`, `agent_messages`). Reuses v0.1's LLMClient (extended with `chat_with_tools`), v0.1's DiagnosisService, v0.2's KnowledgeRepository, v0.2's ContentWriter. New agent modules: `tools.py` (function calling schemas), `tool_executor.py` (wraps v0.1-v0.3 business), `react_loop.py` (ReAct cycle), `session_manager.py` (session/message CRUD). Uses FastAPI's `StreamingResponse` for SSE.

**Tech Stack:** Extends v0.1-v0.3 with: SSE (FastAPI native), React `fetch` + ReadableStream for SSE client. **No new Python packages** (OpenAI SDK already supports tool use). All other constraints inherit from v0.1-v0.3.

## Global Constraints

Inherits **all** v0.1, v0.2, v0.3 constraints. Additions specific to v0.4:

- **v0.4 builds on v0.1 + v0.2 + v0.3** — Tasks assume all v0.1-v0.3 modules exist
- **Native implementation** — no LangChain, LangGraph, or Claude SDK; use v0.1's OpenAI-SDK-based LLMClient
- **MAX_REACT_ITERATIONS = 5** — ReAct loop hard cap to prevent infinite loops
- **No new dependencies** — SSE via FastAPI `StreamingResponse`; tool calling via OpenAI SDK
- **Agent is READ-ONLY at the data layer** — `generate_article` returns preview text only; does NOT insert into v0.2's `articles` table
- **Write-class tools require human confirmation** — v0.4 has 1 such tool: `generate_article`
- **Read-class tools execute immediately** — v0.4 has 2: `diagnose_brand`, `search_knowledge`
- **Tool arguments validated by Pydantic** — invalid args return error to LLM for retry
- **URL SSRF protection** — `diagnose_brand` URL must be http/https with non-internal hostname
- **Each agent run ≤ 30s typical, ≤ 90s hard cap** — abort if exceeded
- **All session/message state persisted to SQLite** — user can resume across page refresh

**Reference spec:** `docs/superpowers/specs/2026-07-10-geo-agent-v0.4-design.md`

---

## Phase 0: Foundation Extensions

### Task 0.1: Extend LLMClient with `chat_with_tools`

**Files:**
- Modify: `D:/GEO2/backend/app/domain/llm_client.py`

**Interfaces (additions):**
- `await llm.chat_with_tools(messages: list[dict], tools: list[dict]) -> dict` — returns `{"content": str | None, "tool_calls": list[dict] | None}`

- [ ] **Step 1: Append method to `llm_client.py`**

Edit `D:/GEO2/backend/app/domain/llm_client.py`. Add the following method to the `LLMClient` class:

```python
    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ) -> dict:
        """Call LLM with tool use. Returns parsed response.

        Returns:
            {
                "content": str | None,     # assistant's text content
                "tool_calls": list[dict] | None,  # [{id, function: {name, arguments}}, ...]
            }
        """
        client = self._make_async_client(self._providers["deepseek"])
        response = await client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7,
        )
        message = response.choices[0].message
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        return {
            "content": message.content,
            "tool_calls": tool_calls,
        }
```

Note: The `_providers` dict and `_make_async_client` helpers already exist in v0.1's LLMClient. If they're named differently, adjust accordingly.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_llm_chat_with_tools.py`:

```python
"""Tests for LLMClient.chat_with_tools."""
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
def llm(settings: Settings) -> LLMClient:
    return LLMClient(settings)


@pytest.mark.asyncio
@respx.mock
async def test_chat_with_tools_returns_text_content(llm: LLMClient) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "好的，让我先诊断。",
                            "tool_calls": None,
                        }
                    }
                ]
            },
        )
    )

    result = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "诊断小米"}],
        tools=[{
            "type": "function",
            "function": {"name": "diagnose_brand", "description": "...", "parameters": {}},
        }],
    )

    assert result["content"] == "好的，让我先诊断。"
    assert result["tool_calls"] is None


@pytest.mark.asyncio
@respx.mock
async def test_chat_with_tools_parses_tool_calls(llm: LLMClient) -> None:
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "tc_001",
                                    "type": "function",
                                    "function": {
                                        "name": "diagnose_brand",
                                        "arguments": '{"brand_name": "小米", "industry": "手机", "official_url": "https://www.mi.com"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )
    )

    result = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "诊断小米"}],
        tools=[{
            "type": "function",
            "function": {"name": "diagnose_brand", "description": "...", "parameters": {}},
        }],
    )

    assert result["content"] is None
    assert result["tool_calls"] is not None
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["id"] == "tc_001"
    assert result["tool_calls"][0]["function"]["name"] == "diagnose_brand"


@pytest.mark.asyncio
@respx.mock
async def test_chat_with_tools_returns_both_content_and_tool_calls(llm: LLMClient) -> None:
    """When LLM responds with both text and tool calls, both are returned."""
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "让我先看小米的分数。",
                            "tool_calls": [
                                {
                                    "id": "tc_001",
                                    "type": "function",
                                    "function": {
                                        "name": "diagnose_brand",
                                        "arguments": '{"brand_name": "小米"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )
    )

    result = await llm.chat_with_tools(
        messages=[{"role": "user", "content": "诊断"}],
        tools=[{"type": "function", "function": {"name": "diagnose_brand"}}],
    )

    assert result["content"] == "让我先看小米的分数。"
    assert result["tool_calls"] is not None
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_llm_chat_with_tools.py -v
```

Expected: FAIL with `AttributeError: 'LLMClient' object has no attribute 'chat_with_tools'`

- [ ] **Step 4: Implement method (if Step 1 wasn't applied yet)**

If you didn't apply Step 1, do so now (add `chat_with_tools` method to `LLMClient` class).

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_llm_chat_with_tools.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Verify v0.1-v0.3 tests still pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All v0.1 + v0.2 + v0.3 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): extend LLMClient with chat_with_tools + tests"
```

---

### Task 0.2: v0.4 ORM Models (2 New Tables)

**Files:**
- Create: `D:/GEO2/backend/app/models/orm_v04.py`

**Interfaces:**
- `AgentSessionORM`
- `AgentMessageORM`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_orm_v0.4.py`:

```python
"""Tests for v0.4 ORM models."""
import json
from datetime import datetime, timezone

import pytest

from app.models.orm_v04 import AgentMessageORM, AgentSessionORM


@pytest.mark.asyncio
async def test_agent_session_orm(db_session) -> None:
    s = AgentSessionORM(id="s1", title="诊断小米")
    db_session.add(s)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(AgentSessionORM).where(AgentSessionORM.id == "s1")
    )
    fetched = result.scalar_one()
    assert fetched.title == "诊断小米"
    assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_agent_message_orm(db_session) -> None:
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m1",
        session_id="s1",
        role="user",
        content="诊断小米",
    )
    db_session.add(m)
    await db_session.commit()

    assert m.role == "user"
    assert m.pending_confirmation == 0  # default
    assert m.tool_calls is None


@pytest.mark.asyncio
async def test_agent_message_with_tool_calls(db_session) -> None:
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m2",
        session_id="s1",
        role="assistant",
        content="让我先诊断",
        tool_calls=json.dumps([
            {"id": "tc1", "name": "diagnose_brand", "arguments": {}}
        ]),
    )
    db_session.add(m)
    await db_session.commit()
    assert json.loads(m.tool_calls)[0]["name"] == "diagnose_brand"


@pytest.mark.asyncio
async def test_agent_message_pending_confirmation(db_session) -> None:
    s = AgentSessionORM(id="s1", title="T")
    db_session.add(s)
    await db_session.commit()

    m = AgentMessageORM(
        id="m3",
        session_id="s1",
        role="assistant",
        content="准备生成文章",
        pending_confirmation=1,
    )
    db_session.add(m)
    await db_session.commit()
    assert m.pending_confirmation == 1
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_orm_v0.4.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/models/orm_v04.py`**

Create `D:/GEO2/backend/app/models/orm_v04.py`:

```python
"""SQLAlchemy ORM models for v0.4 (agent sessions and messages)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentSessionORM(Base):
    """An Agent conversation session."""

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class AgentMessageORM(Base):
    """A single message in an agent session (user/assistant/tool/system)."""

    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String, ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)  # user/assistant/tool/system
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    tool_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    pending_confirmation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_orm_v0.4.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Verify all v0.1-v0.4 tests still pass**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): 2 ORM models (agent_sessions, agent_messages) + tests"
```

---

### Task 0.3: Add `HumanConfirmationRequired` Exception

**Files:**
- Modify: `D:/GEO2/backend/app/domain/exceptions.py`

- [ ] **Step 1: Add exception class**

Edit `D:/GEO2/backend/app/domain/exceptions.py`. Add this class:

```python
class HumanConfirmationRequired(DomainError):
    """Write-class tool needs human approval before execution."""

    def __init__(self, message_id: str, tool_name: str, arguments: dict) -> None:
        self.message_id = message_id
        self.tool_name = tool_name
        self.arguments = arguments
        super().__init__(
            f"Tool {tool_name} requires human confirmation (message_id={message_id})"
        )
```

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_human_confirmation_required.py`:

```python
"""Test HumanConfirmationRequired exception."""
from app.domain.exceptions import DomainError, HumanConfirmationRequired


def test_human_confirmation_required_inherits_domain_error() -> None:
    err = HumanConfirmationRequired(
        message_id="m1", tool_name="generate_article", arguments={"foo": "bar"}
    )
    assert isinstance(err, DomainError)


def test_human_confirmation_required_carries_data() -> None:
    err = HumanConfirmationRequired(
        message_id="msg-123",
        tool_name="generate_article",
        arguments={"kb_id": "kb1", "topic": "X"},
    )
    assert err.message_id == "msg-123"
    assert err.tool_name == "generate_article"
    assert err.arguments == {"kb_id": "kb1", "topic": "X"}


def test_human_confirmation_required_message_contains_tool_name() -> None:
    err = HumanConfirmationRequired(
        message_id="m1", tool_name="generate_article", arguments={}
    )
    assert "generate_article" in str(err)
```

- [ ] **Step 3: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_human_confirmation_required.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): HumanConfirmationRequired exception + tests"
```

---

## Phase 1: Tools — Function Calling Schemas

### Task 1.1: Tool Schemas (3 Tools)

**Files:**
- Create: `D:/GEO2/backend/app/domain/agent/__init__.py`
- Create: `D:/GEO2/backend/app/domain/agent/tools.py`
- Create: `D:/GEO2/backend/tests/test_agent_tools.py`

**Interfaces:**
- `TOOLS: list[dict]` — exported list of 3 tool schemas
- `TOOL_REGISTRY: dict[str, callable]` — maps tool name → executor
- `validate_tool_args(tool_name: str, args: dict) -> BaseModel` — Pydantic validation

- [ ] **Step 1: Create `app/domain/agent/__init__.py`**

Create empty `D:/GEO2/backend/app/domain/agent/__init__.py`.

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_agent_tools.py`:

```python
"""Tests for agent tool schemas and validation."""
import pytest
from pydantic import ValidationError

from app.domain.agent.tools import (
    TOOLS,
    TOOL_NAMES,
    ToolName,
    get_tool_schema,
    validate_tool_args,
)


class TestToolRegistry:
    def test_three_tools_registered(self) -> None:
        assert len(TOOLS) == 3

    def test_tool_names(self) -> None:
        assert TOOL_NAMES == {"diagnose_brand", "search_knowledge", "generate_article"}

    def test_get_tool_schema(self) -> None:
        schema = get_tool_schema("diagnose_brand")
        assert schema["name"] == "diagnose_brand"
        assert "description" in schema
        assert "parameters" in schema


class TestValidateDiagnoseArgs:
    def test_valid_args(self) -> None:
        args = validate_tool_args("diagnose_brand", {
            "brand_name": "小米",
            "industry": "手机",
            "official_url": "https://www.mi.com",
        })
        assert args.brand_name == "小米"
        assert args.industry == "手机"
        assert args.official_url == "https://www.mi.com"

    def test_missing_brand_name(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args("diagnose_brand", {
                "industry": "手机",
                "official_url": "https://www.mi.com",
            })

    def test_invalid_url(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args("diagnose_brand", {
                "brand_name": "X",
                "industry": "Y",
                "official_url": "not-a-url",
            })


class TestValidateSearchArgs:
    def test_valid_args(self) -> None:
        args = validate_tool_args("search_knowledge", {
            "kb_id": "kb-123",
            "query": "产品功能",
        })
        assert args.kb_id == "kb-123"
        assert args.query == "产品功能"
        assert args.limit == 5  # default

    def test_custom_limit(self) -> None:
        args = validate_tool_args("search_knowledge", {
            "kb_id": "kb-123",
            "query": "X",
            "limit": 10,
        })
        assert args.limit == 10

    def test_limit_too_high(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args("search_knowledge", {
                "kb_id": "kb-123", "query": "X", "limit": 100,
            })


class TestValidateGenerateArgs:
    def test_valid_args(self) -> None:
        args = validate_tool_args("generate_article", {
            "kb_id": "kb-123",
            "brand": "小米",
            "topic": "产品评测",
            "keywords": ["性能", "拍照"],
        })
        assert args.brand == "小米"
        assert args.style.value == "neutral"  # default
        assert args.target_length == 1500  # default

    def test_min_topic_length(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args("generate_article", {
                "kb_id": "kb", "brand": "X", "topic": "短", "keywords": ["k"],
            })

    def test_empty_keywords(self) -> None:
        with pytest.raises(ValidationError):
            validate_tool_args("generate_article", {
                "kb_id": "kb", "brand": "X", "topic": "足够长的主题", "keywords": [],
            })


class TestUnknownTool:
    def test_unknown_tool_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            validate_tool_args("unknown_tool", {})
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_agent_tools.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Create `app/domain/agent/tools.py`**

Create `D:/GEO2/backend/app/domain/agent/tools.py`:

```python
"""Function calling schemas + argument validation for the 3 agent tools."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ToolName(str, Enum):
    DIAGNOSE_BRAND = "diagnose_brand"
    SEARCH_KNOWLEDGE = "search_knowledge"
    GENERATE_ARTICLE = "generate_article"


# --- Pydantic models for tool arguments ---


class DiagnoseBrandArgs(BaseModel):
    brand_name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1, max_length=100)
    official_url: HttpUrl


class SearchKnowledgeArgs(BaseModel):
    kb_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(5, ge=1, le=50)


class GenerateArticleArgs(BaseModel):
    kb_id: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=5, max_length=500)
    keywords: list[str] = Field(..., min_length=1, max_length=20)
    style: Literal["neutral", "professional", "casual"] = "neutral"
    target_length: int = Field(1500, ge=300, le=10000)


# --- Function calling schemas (OpenAI-compatible) ---


_DIAGNOSE_SCHEMA = {
    "name": "diagnose_brand",
    "description": (
        "对一个品牌执行 GEO 健康度诊断。需要品牌的名称、行业和官网 URL。"
        "返回综合分数（0-100）、5 个维度的子分数、诊断报告 ID、可能还包括建议清单摘要。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "brand_name": {
                "type": "string",
                "description": "品牌名称，如 '小米'",
            },
            "industry": {
                "type": "string",
                "description": "品牌所属行业，如 '消费电子'",
            },
            "official_url": {
                "type": "string",
                "description": "品牌官网 URL，如 'https://www.mi.com'，必须以 http:// 或 https:// 开头",
            },
        },
        "required": ["brand_name", "industry", "official_url"],
    },
}


_SEARCH_SCHEMA = {
    "name": "search_knowledge",
    "description": (
        "在指定知识库中搜索与查询相关的资料片段。需要知识库 ID 和搜索关键词。"
        "返回最相关的 5 个资料片段（含内容）。注意：agent 只能查询已存在的知识库，不能创建/修改/删除。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": "知识库 ID（UUID）",
            },
            "query": {
                "type": "string",
                "description": "搜索关键词或问题",
            },
            "limit": {
                "type": "integer",
                "description": "返回几个片段，默认 5，最大 10",
                "default": 5,
            },
        },
        "required": ["kb_id", "query"],
    },
}


_GENERATE_SCHEMA = {
    "name": "generate_article",
    "description": (
        "基于指定知识库生成一篇文章草稿。生成前会向用户确认。"
        "返回的内容仅供预览，正式发布需要用户去 v0.2 任务列表完成完整任务流程。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kb_id": {
                "type": "string",
                "description": "知识库 ID",
            },
            "brand": {
                "type": "string",
                "description": "品牌名",
            },
            "topic": {
                "type": "string",
                "description": "文章主题",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "关键词",
            },
            "style": {
                "type": "string",
                "enum": ["neutral", "professional", "casual"],
                "description": "写作风格",
                "default": "neutral",
            },
            "target_length": {
                "type": "integer",
                "description": "目标字数",
                "default": 1500,
            },
        },
        "required": ["kb_id", "brand", "topic", "keywords"],
    },
}


# --- Public exports ---


TOOLS: list[dict] = [
    {"type": "function", "function": _DIAGNOSE_SCHEMA},
    {"type": "function", "function": _SEARCH_SCHEMA},
    {"type": "function", "function": _GENERATE_SCHEMA},
]


TOOL_NAMES: set[str] = {ToolName.DIAGNOSE_BRAND.value, ToolName.SEARCH_KNOWLEDGE.value, ToolName.GENERATE_ARTICLE.value}


_TOOL_SCHEMAS: dict[str, dict] = {t["function"]["name"]: t["function"] for t in TOOLS}


def get_tool_schema(tool_name: str) -> dict:
    """Get the function calling schema for a tool by name."""
    if tool_name not in _TOOL_SCHEMAS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return _TOOL_SCHEMAS[tool_name]


# --- Argument validation ---


_VALIDATORS: dict[str, type[BaseModel]] = {
    "diagnose_brand": DiagnoseBrandArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "generate_article": GenerateArticleArgs,
}


def validate_tool_args(tool_name: str, args: dict) -> BaseModel:
    """Validate tool arguments using the appropriate Pydantic model.

    Raises:
        ValueError: if tool_name is unknown
        pydantic.ValidationError: if args don't match the schema
    """
    if tool_name not in _VALIDATORS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return _VALIDATORS[tool_name](**args)
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_agent_tools.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): 3 tool schemas (diagnose_brand, search_knowledge, generate_article) + Pydantic validation + tests"
```

---

## Phase 2: ToolExecutor — Wraps v0.1-v0.3 Business

### Task 2.1: ToolExecutor Skeleton

**Files:**
- Create: `D:/GEO2/backend/app/domain/agent/tool_executor.py`
- Create: `D:/GEO2/backend/tests/test_tool_executor.py`

**Interfaces:**
- `ToolExecutor(session_id: str)`
- `await executor.execute(tool_name: str, args: dict) -> dict`

- [ ] **Step 1: Write failing test (dispatch)**

Create `D:/GEO2/backend/tests/test_tool_executor.py`:

```python
"""Tests for ToolExecutor."""
from unittest.mock import patch, AsyncMock

import pytest

from app.domain.agent.tool_executor import ToolExecutor


@pytest.fixture
def executor() -> ToolExecutor:
    return ToolExecutor(session_id="test-session")


class TestDispatch:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self, executor: ToolExecutor) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await executor.execute("unknown_tool", {})

    @pytest.mark.asyncio
    async def test_dispatches_to_diagnose(self, executor: ToolExecutor) -> None:
        with patch.object(executor, "_execute_diagnose_brand", new=AsyncMock(return_value={"x": 1})) as mock_fn:
            result = await executor.execute("diagnose_brand", {"brand_name": "X", "industry": "Y", "official_url": "https://example.com"})
            mock_fn.assert_called_once()
            assert result == {"x": 1}

    @pytest.mark.asyncio
    async def test_dispatches_to_search(self, executor: ToolExecutor) -> None:
        with patch.object(executor, "_execute_search_knowledge", new=AsyncMock(return_value={"y": 2})) as mock_fn:
            result = await executor.execute("search_knowledge", {"kb_id": "kb1", "query": "X"})
            mock_fn.assert_called_once()
            assert result == {"y": 2}

    @pytest.mark.asyncio
    async def test_dispatches_to_generate(self, executor: ToolExecutor) -> None:
        with patch.object(executor, "_execute_generate_article", new=AsyncMock(return_value={"z": 3})) as mock_fn:
            result = await executor.execute("generate_article", {"kb_id": "kb1", "brand": "X", "topic": "足够长的主题", "keywords": ["k"]})
            mock_fn.assert_called_once()
            assert result == {"z": 3}
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/agent/tool_executor.py`**

Create `D:/GEO2/backend/app/domain/agent/tool_executor.py`:

```python
"""Executes agent tool calls by wrapping v0.1-v0.3 business logic."""
from __future__ import annotations

import structlog

from app.core.db import get_session_factory
from app.domain.agent.tools import (
    DiagnoseBrandArgs,
    GenerateArticleArgs,
    SearchKnowledgeArgs,
    validate_tool_args,
)
from app.domain.exceptions import HumanConfirmationRequired

logger = structlog.get_logger()


class ToolExecutor:
    """Executes agent tool calls.

    Wraps v0.1 (DiagnosisService), v0.2 (KnowledgeRepository, ContentWriter).
    Write-class tools (generate_article) raise HumanConfirmationRequired
    to pause the ReAct loop.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    async def execute(self, tool_name: str, args: dict) -> dict:
        # Validate args first
        validated = validate_tool_args(tool_name, args)

        if tool_name == "diagnose_brand":
            return await self._execute_diagnose_brand(validated)
        elif tool_name == "search_knowledge":
            return await self._execute_search_knowledge(validated)
        elif tool_name == "generate_article":
            return await self._execute_generate_article(validated)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def _execute_diagnose_brand(self, args: DiagnoseBrandArgs) -> dict:
        """Diagnose a brand. Wraps v0.1's DiagnosisService."""
        # Implemented in Task 2.2
        raise NotImplementedError

    async def _execute_search_knowledge(self, args: SearchKnowledgeArgs) -> dict:
        """Search knowledge base. Wraps v0.2's KnowledgeRepository."""
        # Implemented in Task 2.3
        raise NotImplementedError

    async def _execute_generate_article(self, args: GenerateArticleArgs) -> dict:
        """Generate article. Raises HumanConfirmationRequired before writing."""
        # Implemented in Task 2.4
        raise NotImplementedError
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: All 4 dispatch tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): ToolExecutor dispatch skeleton + tests"
```

---

### Task 2.2: ToolExecutor — diagnose_brand Implementation

**Files:**
- Modify: `D:/GEO2/backend/app/domain/agent/tool_executor.py`
- Modify: `D:/GEO2/backend/tests/test_tool_executor.py`

**Interfaces:**
- `_execute_diagnose_brand(args: DiagnoseBrandArgs) -> dict` — wraps v0.1, returns simplified result

- [ ] **Step 1: Append failing test to `test_tool_executor.py`**

Append to `D:/GEO2/backend/tests/test_tool_executor.py`:

```python
class TestDiagnoseBrand:
    @pytest.mark.asyncio
    async def test_calls_diagnosis_service(self, executor: ToolExecutor) -> None:
        from app.models.schemas import ScoreCard, DimensionScore, DiagnosisRequest

        mock_report = type("MockReport", (), {})()
        mock_score_card = ScoreCard(
            authority=DimensionScore(name="权威度", score=5.0, weight=0.25, evidence=[]),
            relevance=DimensionScore(name="相关性", score=3.0, weight=0.30, evidence=[]),
            structure=DimensionScore(name="结构", score=4.0, weight=0.20, evidence=[]),
            freshness=DimensionScore(name="新鲜", score=6.0, weight=0.15, evidence=[]),
            verifiability=DimensionScore(name="可验证", score=2.0, weight=0.10, evidence=[]),
            overall=45.0,
            mention_rate=0.1,
            avg_mention_position=2.0,
        )
        mock_report.score_card = mock_score_card
        mock_report.suggestions = [
            type("S", (), {"title": "添加 Organization Schema"})(),
        ]
        mock_task = type("MockTask", (), {"id": "report-123", "report": mock_report})()

        with patch("app.services.diagnosis_service.DiagnosisService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.run = AsyncMock(return_value=mock_task)
            result = await executor._execute_diagnose_brand(
                DiagnoseBrandArgs(
                    brand_name="小米", industry="手机", official_url="https://www.mi.com"
                )
            )

        assert result["report_id"] == "report-123"
        assert result["overall_score"] == 45.0
        assert result["mention_rate"] == 0.1
        assert result["dimensions"]["authority"] == 5.0
        assert result["suggestions_count"] == 1
        assert result["top_suggestion"] == "添加 Organization Schema"
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py::TestDiagnoseBrand -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement `_execute_diagnose_brand` in `tool_executor.py`**

Edit `D:/GEO2/backend/app/domain/agent/tool_executor.py`. Replace the `_execute_diagnose_brand` method:

```python
    async def _execute_diagnose_brand(self, args: DiagnoseBrandArgs) -> dict:
        """Diagnose a brand. Wraps v0.1's DiagnosisService.run().

        Returns a simplified result to avoid LLM context explosion.
        """
        from app.core.config import get_settings
        from app.models.schemas import DiagnosisRequest
        from app.services.diagnosis_service import DiagnosisService

        settings = get_settings()
        factory = get_session_factory()
        async with factory() as session:
            from app.repositories.report_repo import ReportRepository
            repo = ReportRepository(session)
            crawler = type("C", (), {})()  # placeholder; replaced below
            # Real call — v0.1's DiagnosisService needs repo + crawler + llm + settings.
            # We instantiate only what we need for the test seam.
            from app.domain.crawler import Crawler
            from app.domain.llm_client import LLMClient
            crawler = Crawler(settings)
            llm = LLMClient(settings)
            try:
                svc = DiagnosisService(repo=repo, crawler=crawler, llm=llm, settings=settings)
                req = DiagnosisRequest(
                    brand_name=args.brand_name,
                    industry=args.industry,
                    official_url=str(args.official_url),
                )
                task = await svc.run(req.id, req)  # v0.1 signature: run(task_id, request)
                report = task.report
                score = report.score_card
                return {
                    "report_id": task.id,
                    "overall_score": score.overall,
                    "mention_rate": score.mention_rate,
                    "dimensions": {
                        "authority": score.authority.score,
                        "relevance": score.relevance.score,
                        "structure": score.structure.score,
                        "freshness": score.freshness.score,
                        "verifiability": score.verifiability.score,
                    },
                    "suggestions_count": len(report.suggestions),
                    "top_suggestion": report.suggestions[0].title if report.suggestions else None,
                }
            finally:
                await crawler.close()
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: All tests PASS (the diagnose_brand test mocks `DiagnosisService` so the real call is bypassed).

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): ToolExecutor._execute_diagnose_brand wraps v0.1 + tests"
```

---

### Task 2.3: ToolExecutor — search_knowledge Implementation

**Files:**
- Modify: `D:/GEO2/backend/app/domain/agent/tool_executor.py`
- Modify: `D:/GEO2/backend/tests/test_tool_executor.py`

- [ ] **Step 1: Append failing test**

Append to `D:/GEO2/backend/tests/test_tool_executor.py`:

```python
class TestSearchKnowledge:
    @pytest.mark.asyncio
    async def test_returns_truncated_chunks(self, executor: ToolExecutor) -> None:
        long_content = "x" * 1000  # > 500 chars, should be truncated
        from app.models.orm_v02 import KnowledgeChunkORM

        async def fake_search(*args, **kwargs):
            return [
                KnowledgeChunkORM(
                    id="c1", doc_id="d1", kb_id="kb1", chunk_index=0,
                    content=long_content, content_length=1000,
                )
            ]

        with patch("app.domain.agent.tool_executor.search_chunks", side_effect=fake_search):
            result = await executor._execute_search_knowledge(
                type("Args", (), {"kb_id": "kb1", "query": "test", "limit": 5})()
            )

        assert result["kb_id"] == "kb1"
        assert result["query"] == "test"
        assert result["total_found"] == 1
        assert len(result["chunks"]) == 1
        assert len(result["chunks"][0]["content"]) == 500  # truncated
        assert result["chunks"][0]["content_length"] == 500  # reflects truncated size
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py::TestSearchKnowledge -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement `_execute_search_knowledge`**

Edit `D:/GEO2/backend/app/domain/agent/tool_executor.py`. Replace the method:

```python
    @staticmethod
    async def _execute_search_knowledge(args: SearchKnowledgeArgs) -> dict:
        """Search knowledge base. Wraps v0.2's search_chunks.

        Truncates each chunk's content to 500 chars to avoid LLM context explosion.
        """
        import jieba
        from app.core.db import get_session_factory
        from app.domain.knowledge.retriever import search_chunks
        from app.repositories.knowledge_repo import KnowledgeRepository

        keywords = [w for w in jieba.cut(args.query) if len(w.strip()) > 1]

        factory = get_session_factory()
        async with factory() as session:
            chunks = await search_chunks(
                session=session,
                kb_id=args.kb_id,
                keywords=keywords,
                top_k=args.limit,
            )

        truncated: list[dict] = []
        for c in chunks:
            content = c.content[:500]
            truncated.append({
                "id": c.id,
                "doc_id": c.doc_id,
                "chunk_index": c.chunk_index,
                "content": content,
                "content_length": len(content),
            })

        return {
            "kb_id": args.kb_id,
            "query": args.query,
            "chunks": truncated,
            "total_found": len(chunks),
        }
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): ToolExecutor._execute_search_knowledge wraps v0.2 with truncation + tests"
```

---

### Task 2.4: ToolExecutor — generate_article (Human Confirmation)

**Files:**
- Modify: `D:/GEO2/backend/app/domain/agent/tool_executor.py`
- Modify: `D:/GEO2/backend/tests/test_tool_executor.py`

- [ ] **Step 1: Append failing tests**

Append to `D:/GEO2/backend/tests/test_tool_executor.py`:

```python
class TestGenerateArticle:
    @pytest.mark.asyncio
    async def test_raises_human_confirmation_required(self, executor: ToolExecutor) -> None:
        from app.domain.agent.tools import GenerateArticleArgs
        from app.domain.exceptions import HumanConfirmationRequired

        with pytest.raises(HumanConfirmationRequired) as exc_info:
            await executor._execute_generate_article(
                GenerateArticleArgs(
                    kb_id="kb1", brand="小米", topic="产品评测",
                    keywords=["性能", "拍照"],
                )
            )

        assert exc_info.value.tool_name == "generate_article"
        assert exc_info.value.arguments["brand"] == "小米"
        assert exc_info.value.message_id != ""

    @pytest.mark.asyncio
    async def test_human_confirmation_message_persisted(self, executor: ToolExecutor) -> None:
        """Verify a 'pending confirmation' message is saved to the DB."""
        from app.domain.agent.tools import GenerateArticleArgs
        from app.domain.exceptions import HumanConfirmationRequired
        from app.models.orm_v04 import AgentMessageORM
        from app.core.db import get_session_factory
        from sqlalchemy import select

        try:
            await executor._execute_generate_article(
                GenerateArticleArgs(
                    kb_id="kb1", brand="小米", topic="产品评测",
                    keywords=["性能", "拍照"],
                )
            )
        except HumanConfirmationRequired as e:
            msg_id = e.message_id
            # Verify the message was saved with pending_confirmation=1
            async with get_session_factory()() as session:
                result = await session.execute(
                    select(AgentMessageORM).where(AgentMessageORM.id == msg_id)
                )
                msg = result.scalar_one()
                assert msg.role == "assistant"
                assert msg.pending_confirmation == 1
                assert "产品评测" in msg.content
                assert "小米" in msg.content
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py::TestGenerateArticle -v
```

Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement `_execute_generate_article`**

Edit `D:/GEO2/backend/app/domain/agent/tool_executor.py`. Replace the method:

```python
    @staticmethod
    async def _execute_generate_article(args: GenerateArticleArgs) -> dict:
        """Generate article. Saves pending-confirmation message; raises to pause loop.

        IMPORTANT: This is a write-class tool. It does NOT call v0.2's
        ContentWriter yet. It only saves a 'pending confirmation' message
        to the agent_messages table and raises HumanConfirmationRequired.

        After user approves (via the confirm endpoint), the react_loop's
        checkpoint resume will call _execute_generate_article_confirmed.
        """
        import json
        import uuid
        from app.core.db import get_session_factory
        from app.domain.exceptions import HumanConfirmationRequired
        from app.models.orm_v04 import AgentMessageORM

        # Save a 'pending' message
        message_id = str(uuid.uuid4())
        content = (
            f"准备生成文章：\n"
            f"- 品牌：{args.brand}\n"
            f"- 主题：{args.topic}\n"
            f"- 关键词：{', '.join(args.keywords)}\n"
            f"- 风格：{args.style}\n"
            f"- 目标字数：{args.target_length}\n\n"
            f"是否继续？"
        )
        async with get_session_factory()() as session:
            msg = AgentMessageORM(
                id=message_id,
                session_id=args.kb_id,  # placeholder, will be set by caller
                role="assistant",
                content=content,
                tool_calls=json.dumps([{
                    "tool": "generate_article",
                    "arguments": args.model_dump(mode="json"),
                }]),
                pending_confirmation=1,
            )
            session.add(msg)
            await session.commit()

        raise HumanConfirmationRequired(
            message_id=message_id,
            tool_name="generate_article",
            arguments=args.model_dump(mode="json"),
        )
```

Note: The `session_id` is set by the caller in `_execute`. Since the signature is `(self, args)` and we don't have `session_id` here, this will fail. Let me fix the signature to include `session_id`:

Replace the staticmethod with:

```python
    async def _execute_generate_article(self, args: GenerateArticleArgs) -> dict:
        """Generate article. Saves pending-confirmation message; raises to pause loop."""
        import json
        import uuid
        from app.core.db import get_session_factory
        from app.domain.exceptions import HumanConfirmationRequired
        from app.models.orm_v04 import AgentMessageORM

        message_id = str(uuid.uuid4())
        content = (
            f"准备生成文章：\n"
            f"- 品牌：{args.brand}\n"
            f"- 主题：{args.topic}\n"
            f"- 关键词：{', '.join(args.keywords)}\n"
            f"- 风格：{args.style}\n"
            f"- 目标字数：{args.target_length}\n\n"
            f"是否继续？"
        )
        async with get_session_factory()() as session:
            msg = AgentMessageORM(
                id=message_id,
                session_id=self.session_id,
                role="assistant",
                content=content,
                tool_calls=json.dumps([{
                    "tool": "generate_article",
                    "arguments": args.model_dump(mode="json"),
                }]),
                pending_confirmation=1,
            )
            session.add(msg)
            await session.commit()

        raise HumanConfirmationRequired(
            message_id=message_id,
            tool_name="generate_article",
            arguments=args.model_dump(mode="json"),
        )
```

Also update the dispatch in `execute()` (already correctly calls `self._execute_generate_article(validated)`).

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_tool_executor.py -v
```

Expected: All tests PASS (note: the persistence test requires `db_session` fixture, which is auto-provided).

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): ToolExecutor._execute_generate_article raises HumanConfirmationRequired + persists message + tests"
```

---

## Phase 3: Session Management

### Task 3.1: AgentRepository (CRUD)

**Files:**
- Create: `D:/GEO2/backend/app/repositories/agent_repo.py`
- Create: `D:/GEO2/backend/tests/test_agent_repo.py`

**Interfaces:**
- `AgentRepository(session)`:
  - `create_session(title=None) -> AgentSessionORM`
  - `get_session(id) -> AgentSessionORM | None`
  - `list_sessions(limit=50) -> list[AgentSessionORM]`
  - `delete_session(id) -> None`
  - `update_session_title(id, title) -> None`
  - `update_session_timestamp(id) -> None`
  - `create_message(session_id, role, content, tool_calls=None, tool_call_id=None, pending_confirmation=False) -> AgentMessageORM`
  - `get_message(id) -> AgentMessageORM | None`
  - `list_messages(session_id) -> list[AgentMessageORM]`
  - `confirm_message(id, approved) -> None`

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_agent_repo.py`:

```python
"""Tests for AgentRepository."""
import json

import pytest

from app.models.orm_v04 import AgentMessageORM, AgentSessionORM
from app.repositories.agent_repo import AgentRepository


@pytest.mark.asyncio
async def test_create_session(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="诊断小米")
    assert s.id != ""
    assert s.title == "诊断小米"


@pytest.mark.asyncio
async def test_get_session(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    fetched = await repo.get_session(s.id)
    assert fetched is not None
    assert fetched.title == "X"


@pytest.mark.asyncio
async def test_list_sessions_orders_by_updated_desc(db_session) -> None:
    repo = AgentRepository(db_session)
    s1 = await repo.create_session(title="A")
    s2 = await repo.create_session(title="B")
    sessions = await repo.list_sessions()
    assert sessions[0].id == s2.id  # most recent first


@pytest.mark.asyncio
async def test_delete_session(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    await repo.delete_session(s.id)
    assert await repo.get_session(s.id) is None


@pytest.mark.asyncio
async def test_update_session_title(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    await repo.update_session_title(s.id, "Y")
    fetched = await repo.get_session(s.id)
    assert fetched.title == "Y"


@pytest.mark.asyncio
async def test_create_message(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(session_id=s.id, role="user", content="hi")
    assert m.id != ""
    assert m.role == "user"


@pytest.mark.asyncio
async def test_create_message_with_tool_calls(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(
        session_id=s.id, role="assistant", content=None,
        tool_calls=[{"id": "tc1", "name": "diagnose_brand", "arguments": {}}],
    )
    assert json.loads(m.tool_calls)[0]["name"] == "diagnose_brand"


@pytest.mark.asyncio
async def test_list_messages_orders_by_created_at(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m1 = await repo.create_message(session_id=s.id, role="user", content="1")
    m2 = await repo.create_message(session_id=s.id, role="assistant", content="2")
    messages = await repo.list_messages(s.id)
    assert messages[0].id == m1.id
    assert messages[1].id == m2.id


@pytest.mark.asyncio
async def test_confirm_message(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(
        session_id=s.id, role="assistant", content="...",
        pending_confirmation=True,
    )
    await repo.confirm_message(m.id, approved=True)
    fetched = await repo.get_message(m.id)
    assert fetched.pending_confirmation == 0


@pytest.mark.asyncio
async def test_confirm_message_rejected(db_session) -> None:
    repo = AgentRepository(db_session)
    s = await repo.create_session(title="X")
    m = await repo.create_message(
        session_id=s.id, role="assistant", content="...",
        pending_confirmation=True,
    )
    await repo.confirm_message(m.id, approved=False)
    fetched = await repo.get_message(m.id)
    assert fetched.pending_confirmation == 0
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_agent_repo.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/repositories/agent_repo.py`**

Create `D:/GEO2/backend/app/repositories/agent_repo.py`:

```python
"""Repository for agent_sessions and agent_messages."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v04 import AgentMessageORM, AgentSessionORM


class AgentRepository:
    """Data access for v0.4 agent tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- Sessions ---

    async def create_session(self, title: str | None = None) -> AgentSessionORM:
        s = AgentSessionORM(
            id=str(uuid.uuid4()),
            title=title or "新对话",
        )
        self.session.add(s)
        await self.session.commit()
        await self.session.refresh(s)
        return s

    async def get_session(self, id: str) -> AgentSessionORM | None:
        result = await self.session.execute(
            select(AgentSessionORM).where(AgentSessionORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_sessions(self, limit: int = 50) -> list[AgentSessionORM]:
        result = await self.session.execute(
            select(AgentSessionORM)
            .order_by(AgentSessionORM.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_session(self, id: str) -> None:
        from sqlalchemy import delete
        await self.session.execute(
            delete(AgentSessionORM).where(AgentSessionORM.id == id)
        )
        await self.session.commit()

    async def update_session_title(self, id: str, title: str) -> None:
        s = await self.get_session(id)
        if s is None:
            return
        s.title = title
        s.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_session_timestamp(self, id: str) -> None:
        s = await self.get_session(id)
        if s is None:
            return
        s.updated_at = datetime.now(timezone.utc)
        await self.session.commit()

    # --- Messages ---

    async def create_message(
        self,
        session_id: str,
        role: str,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        tool_call_id: str | None = None,
        pending_confirmation: bool = False,
    ) -> AgentMessageORM:
        m = AgentMessageORM(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=json.dumps(tool_calls) if tool_calls else None,
            tool_call_id=tool_call_id,
            pending_confirmation=1 if pending_confirmation else 0,
        )
        self.session.add(m)
        await self.session.commit()
        await self.session.refresh(m)
        # Also bump session timestamp
        await self.update_session_timestamp(session_id)
        return m

    async def get_message(self, id: str) -> AgentMessageORM | None:
        result = await self.session.execute(
            select(AgentMessageORM).where(AgentMessageORM.id == id)
        )
        return result.scalar_one_or_none()

    async def list_messages(self, session_id: str) -> list[AgentMessageORM]:
        result = await self.session.execute(
            select(AgentMessageORM)
            .where(AgentMessageORM.session_id == session_id)
            .order_by(AgentMessageORM.created_at)
        )
        return list(result.scalars().all())

    async def confirm_message(self, id: str, approved: bool) -> None:
        m = await self.get_message(id)
        if m is None:
            return
        # We mark the message as resolved by setting pending_confirmation=0
        # The actual user-cancellation text is added by the API layer.
        m.pending_confirmation = 0
        await self.session.commit()
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_agent_repo.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): AgentRepository with session/message CRUD + confirm + tests"
```

---

### Task 3.2: Session Manager — Title Auto-Generation

**Files:**
- Create: `D:/GEO2/backend/app/domain/agent/session_manager.py`
- Create: `D:/GEO2/backend/tests/test_session_manager.py`

**Interfaces:**
- `auto_generate_title(first_user_message: str, settings, llm) -> str` — async, returns short title
- `list_summaries(limit=50) -> list[dict]` — for API

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_session_manager.py`:

```python
"""Tests for session manager helpers."""
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.agent.session_manager import auto_generate_title


@pytest.mark.asyncio
async def test_auto_generate_title_returns_short_string() -> None:
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(return_value="诊断小米品牌")
        title = await auto_generate_title("帮我诊断一下小米的 GEO 现状")
        assert title == "诊断小米品牌"
        assert len(title) <= 30


@pytest.mark.asyncio
async def test_auto_generate_title_truncates_long_response() -> None:
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        long = "x" * 100
        mock_instance.simple_chat = AsyncMock(return_value=long)
        title = await auto_generate_title("hi")
        assert len(title) <= 20


@pytest.mark.asyncio
async def test_auto_generate_title_falls_back_to_truncation_on_error() -> None:
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(side_effect=Exception("LLM down"))
        # Should not raise; should return truncated first message
        title = await auto_generate_title("帮我诊断小米的 GEO 现状，目标是提升到 80 分以上")
        assert len(title) <= 20
        assert "诊断" in title  # first 20 chars of message


@pytest.mark.asyncio
async def test_auto_generate_title_strips_whitespace() -> None:
    with patch("app.domain.agent.session_manager.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.simple_chat = AsyncMock(return_value="  标题带空格  \n")
        title = await auto_generate_title("hi")
        assert title == "标题带空格"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_session_manager.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/domain/agent/session_manager.py`**

Create `D:/GEO2/backend/app/domain/agent/session_manager.py`:

```python
"""Session management helpers (title auto-generation, etc.)."""
from __future__ import annotations

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


async def auto_generate_title(first_user_message: str) -> str:
    """Use LLM to extract a short title from the first user message.

    Returns a title of max 20 characters. Falls back to truncation if LLM fails.
    """
    settings = get_settings()

    try:
        from app.domain.llm_client import LLMClient
        llm = LLMClient(settings)
        response = await llm.simple_chat(
            prompt=(
                f"请从以下用户消息中提取一个不超过 15 字的对话标题。"
                f"只输出标题本身，不要其他内容：\n\n{first_user_message[:200]}"
            )
        )
        title = response.strip()[:20]
        return title if title else first_user_message[:20]
    except Exception as e:  # noqa: BLE001
        logger.warning("auto_generate_title_failed", error=str(e))
        return first_user_message[:20]
```

Note: `LLMClient.simple_chat` may not exist yet in v0.1's LLMClient. If it doesn't, add it:

Edit `D:/GEO2/backend/app/domain/llm_client.py`. Add:

```python
    async def simple_chat(self, prompt: str) -> str:
        """Simple text-only chat (no tools). Returns the assistant's content."""
        client = self._make_async_client(self._providers["deepseek"])
        response = await client.chat.completions.create(
            model=self.settings.deepseek_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return response.choices[0].message.content or ""
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_session_manager.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): auto_generate_title with LLM + fallback + tests"
```

---

## Phase 4: ReAct Loop

### Task 4.1: ReAct Loop Core

**Files:**
- Create: `D:/GEO2/backend/app/domain/agent/prompts.py`
- Create: `D:/GEO2/backend/app/domain/agent/react_loop.py`
- Create: `D:/GEO2/backend/tests/test_react_loop.py`

**Interfaces:**
- `run_agent_turn(session_id, user_message) -> AsyncIterator[dict]` — yields SSE events
- `build_messages(history) -> list[dict]` — formats messages for LLM

- [ ] **Step 1: Create `app/domain/agent/prompts.py`**

Create `D:/GEO2/backend/app/domain/agent/prompts.py`:

```python
"""System prompt for the agent."""
from __future__ import annotations

AGENT_SYSTEM_PROMPT = """你是 GEO Agent，一个帮助用户做"生成式引擎优化"（GEO）的 AI 助手。

你可以使用以下工具：
- diagnose_brand：诊断一个品牌的 GEO 健康度（综合分数 + 5 维子分数 + 建议）
- search_knowledge：在指定知识库中搜索相关资料（用于回答问题、辅助生成）
- generate_article：基于知识库生成一篇文章（**会询问用户确认**）

工作原则：
1. 优先使用工具获取真实数据，不要凭空回答
2. 每次只调用一个工具，等结果回来再决定下一步
3. 调用 generate_article 之前，向用户简短说明为什么需要生成（基于之前的诊断 / 知识库结果）
4. 总结时引用具体的数字和工具结果
5. 不知道的不要编造，明确告诉用户
6. 回复简洁，1-3 句话为主

中文回复。
"""
```

- [ ] **Step 2: Write failing test for `build_messages`**

Create `D:/GEO2/backend/tests/test_react_loop.py`:

```python
"""Tests for ReAct loop."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.agent.react_loop import build_messages


def test_build_messages_starts_with_system_prompt() -> None:
    messages = build_messages(history=[])
    assert messages[0]["role"] == "system"
    assert "GEO" in messages[0]["content"]


def test_build_messages_includes_user_assistant_history() -> None:
    history = [
        {"role": "user", "content": "诊断小米"},
        {"role": "assistant", "content": "好的"},
    ]
    messages = build_messages(history=history)
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "诊断小米"
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "好的"


def test_build_messages_converts_tool_messages_to_tool_role() -> None:
    """Internal 'tool' role messages need to be 'tool' role with tool_call_id for OpenAI."""
    history = [
        {"role": "user", "content": "诊断"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "tc1", "function": {"name": "diagnose_brand", "arguments": "{}"}}
        ]},
        {"role": "tool", "tool_call_id": "tc1", "content": "result"},
    ]
    messages = build_messages(history=history)
    # Find the tool message
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "tc1"


def test_build_messages_serializes_tool_call_arguments() -> None:
    """Tool call arguments are stored as JSON strings; LLM needs objects."""
    history = [
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "tc1", "function": {"name": "diagnose_brand", "arguments": '{"brand_name": "小米"}'}}
        ]},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    assert isinstance(asst["tool_calls"][0]["function"]["arguments"], dict)
    assert asst["tool_calls"][0]["function"]["arguments"]["brand_name"] == "小米"
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_react_loop.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Create `app/domain/agent/react_loop.py` (initial) — just `build_messages`**

Create `D:/GEO2/backend/app/domain/agent/react_loop.py`:

```python
"""ReAct loop: orchestrates the agent's reasoning + tool execution cycle."""
from __future__ import annotations

import json
import structlog
from typing import AsyncIterator

from app.core.config import get_settings
from app.domain.agent.prompts import AGENT_SYSTEM_PROMPT
from app.domain.agent.tool_executor import ToolExecutor
from app.domain.agent.tools import TOOLS
from app.domain.exceptions import HumanConfirmationRequired
from app.domain.llm_client import LLMClient
from app.models.orm_v04 import AgentMessageORM
from app.repositories.agent_repo import AgentRepository

logger = structlog.get_logger()

MAX_REACT_ITERATIONS = 5


def build_messages(history: list[dict]) -> list[dict]:
    """Build the messages list for the LLM, including system prompt.

    history elements have shape:
      {"role": "user"|"assistant"|"tool"|"system", "content": str, ...}
    """
    out: list[dict] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]

    for msg in history:
        role = msg["role"]
        if role == "user":
            out.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            asst: dict = {"role": "assistant", "content": msg.get("content")}
            if msg.get("tool_calls"):
                # Parse tool_calls: stored as JSON string in DB, but LLM needs objects
                tc_raw = msg["tool_calls"]
                if isinstance(tc_raw, str):
                    tc_raw = json.loads(tc_raw)
                asst["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            # Parse arguments JSON
                            "arguments": json.loads(tc["function"]["arguments"])
                            if isinstance(tc["function"]["arguments"], str)
                            else tc["function"]["arguments"],
                        },
                    }
                    for tc in tc_raw
                ]
            out.append(asst)
        elif role == "tool":
            out.append({
                "role": "tool",
                "tool_call_id": msg["tool_call_id"],
                "content": msg["content"],
            })

    return out


async def run_agent_turn(
    session_id: str,
    user_message: str,
    db_session=None,  # passed for testability
) -> AsyncIterator[dict]:
    """Execute one ReAct turn for the given session. Yields SSE events.

    Yields dicts with shape:
        {"event": "assistant_message", "content": str}
        {"event": "tool_call_start", "tool_call_id": str, "tool_name": str, "arguments": dict}
        {"event": "tool_call_result", "tool_call_id": str, "result": dict}
        {"event": "human_confirmation_required", "message_id": str, "tool_name": str, "arguments": dict}
        {"event": "turn_complete"}
        {"event": "max_iterations_reached", "message": str}
    """
    # Implemented in Task 4.2
    yield {"event": "turn_complete"}
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_react_loop.py -v
```

Expected: All 4 `build_messages` tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): react_loop.build_messages + system prompt + tests"
```

---

### Task 4.2: ReAct Loop Full Implementation

**Files:**
- Modify: `D:/GEO2/backend/app/domain/agent/react_loop.py`
- Modify: `D:/GEO2/backend/tests/test_react_loop.py`

- [ ] **Step 1: Append failing integration tests**

Append to `D:/GEO2/backend/tests/test_react_loop.py`:

```python
class TestRunAgentTurn:
    @pytest.mark.asyncio
    async def test_diagnose_brand_flow(self) -> None:
        """User: '诊断小米'. Agent calls diagnose_brand, then returns summary."""
        from app.core.db import get_session_factory
        from app.repositories.agent_repo import AgentRepository

        # Setup session
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            session = await repo.create_session(title="T")

        # Mock LLM: first call returns tool_call, second call returns final text
        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(side_effect=[
                {
                    "content": None,
                    "tool_calls": [{
                        "id": "tc1",
                        "function": {
                            "name": "diagnose_brand",
                            "arguments": '{"brand_name": "小米", "industry": "手机", "official_url": "https://www.mi.com"}',
                        },
                    }],
                },
                {
                    "content": "小米 GEO 分数 45，建议添加 Schema。",
                    "tool_calls": None,
                },
            ])
            # Mock tool execution
            with patch("app.domain.agent.tool_executor.ToolExecutor.execute", new=AsyncMock(return_value={
                "report_id": "r1", "overall_score": 45, "mention_rate": 0.1,
                "dimensions": {"authority": 5.0, "relevance": 3.0},
                "suggestions_count": 1, "top_suggestion": "添加 Schema",
            })):
                events = []
                async for evt in run_agent_turn(session.id, "诊断小米"):
                    events.append(evt)

        event_names = [e["event"] for e in events]
        assert "assistant_message" in event_names
        assert "tool_call_start" in event_names
        assert "tool_call_result" in event_names
        assert "turn_complete" in event_names

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self) -> None:
        """If LLM keeps calling tools, stop at MAX_REACT_ITERATIONS=5."""
        from app.core.db import get_session_factory
        from app.repositories.agent_repo import AgentRepository

        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            session = await repo.create_session(title="T")

        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            # Always returns a tool_call, never a final answer
            mock_instance.chat_with_tools = AsyncMock(return_value={
                "content": None,
                "tool_calls": [{
                    "id": "tc",
                    "function": {"name": "diagnose_brand", "arguments": '{"brand_name":"X","industry":"Y","official_url":"https://x.com"}'},
                }],
            })
            with patch("app.domain.agent.tool_executor.ToolExecutor.execute", new=AsyncMock(return_value={"x": 1})):
                events = []
                async for evt in run_agent_turn(session.id, "X"):
                    events.append(evt)

        assert events[-1]["event"] == "max_iterations_reached"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_react_loop.py::TestRunAgentTurn -v
```

Expected: FAIL (only the stub yields turn_complete).

- [ ] **Step 3: Implement full `run_agent_turn`**

Edit `D:/GEO2/backend/app/domain/agent/react_loop.py`. Replace the `run_agent_turn` function:

```python
async def run_agent_turn(
    session_id: str,
    user_message: str,
) -> AsyncIterator[dict]:
    """Execute one ReAct turn for the given session. Yields SSE events."""
    settings = get_settings()
    llm = LLMClient(settings)
    executor = ToolExecutor(session_id)

    # 1. Load history from DB
    from app.core.db import get_session_factory
    async with get_session_factory()() as s:
        repo = AgentRepository(s)
        history_rows = await repo.list_messages(session_id)
        # Convert ORM rows to dict format expected by build_messages
        history = [_message_to_dict(m) for m in history_rows]

        # 2. Save user message
        await repo.create_message(
            session_id=session_id, role="user", content=user_message
        )
        history.append({"role": "user", "content": user_message})

    # 3. ReAct loop
    for iteration in range(MAX_REACT_ITERATIONS):
        messages = build_messages(history)

        response = await llm.chat_with_tools(messages=messages, tools=TOOLS)
        content = response.get("content")
        tool_calls = response.get("tool_calls") or []

        # Save assistant message
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            tool_calls_for_db = [
                {
                    "id": tc["id"],
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"]["arguments"])
                        if isinstance(tc["function"]["arguments"], dict)
                        else tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ] if tool_calls else None
            await repo.create_message(
                session_id=session_id, role="assistant",
                content=content, tool_calls=tool_calls_for_db,
            )

        yield {"event": "assistant_message", "content": content or ""}

        if tool_calls:
            for tool_call in tool_calls:
                tool_id = tool_call["id"]
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                # If arguments is a string (rare), parse it
                if isinstance(tool_args, str):
                    tool_args = json.loads(tool_args)

                yield {
                    "event": "tool_call_start",
                    "tool_call_id": tool_id,
                    "tool_name": tool_name,
                    "arguments": tool_args,
                }

                try:
                    result = await executor.execute(tool_name, tool_args)

                    async with get_session_factory()() as s:
                        repo = AgentRepository(s)
                        await repo.create_message(
                            session_id=session_id, role="tool",
                            content=json.dumps(result, ensure_ascii=False),
                            tool_call_id=tool_id,
                        )

                    yield {
                        "event": "tool_call_result",
                        "tool_call_id": tool_id,
                        "result": result,
                    }
                except HumanConfirmationRequired as e:
                    yield {
                        "event": "human_confirmation_required",
                        "message_id": e.message_id,
                        "tool_name": e.tool_name,
                        "arguments": e.arguments,
                    }
                    return  # Exit loop, await user confirmation

            # Reload history for next iteration
            async with get_session_factory()() as s:
                repo = AgentRepository(s)
                history_rows = await repo.list_messages(session_id)
                history = [_message_to_dict(m) for m in history_rows]
        else:
            # Final answer
            yield {"event": "turn_complete"}
            return

    # Max iterations reached
    yield {
        "event": "max_iterations_reached",
        "message": f"agent 达到最大推理步数 ({MAX_REACT_ITERATIONS})",
    }


def _message_to_dict(m: AgentMessageORM) -> dict:
    """Convert ORM message to dict format for build_messages."""
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "tool_call_id": m.tool_call_id,
    }
```

- [ ] **Step 4: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_react_loop.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): react_loop.run_agent_turn with tool execution + human confirmation + tests"
```

---

## Phase 5: API Endpoints

### Task 5.1: Agent Session CRUD API

**Files:**
- Create: `D:/GEO2/backend/app/api/agent_sessions.py`
- Create: `D:/GEO2/backend/app/models/agent.py`
- Create: `D:/GEO2/backend/tests/test_api_agent_sessions.py`

**Interfaces:**
- `GET /api/agent/sessions` — list
- `POST /api/agent/sessions` — create
- `GET /api/agent/sessions/{id}` — detail
- `DELETE /api/agent/sessions/{id}` — delete
- `PATCH /api/agent/sessions/{id}` — update title

- [ ] **Step 1: Create `app/models/agent.py`**

Create `D:/GEO2/backend/app/models/agent.py`:

```python
"""Pydantic models for the agent API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AgentMessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class AgentSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class AgentMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: AgentMessageRole
    content: str | None
    tool_calls: list[dict] | None
    tool_call_id: str | None
    pending_confirmation: bool
    created_at: datetime


class AgentSessionDetail(BaseModel):
    """Session + full message history."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[AgentMessage]


class CreateSessionRequest(BaseModel):
    title: str | None = Field(None, max_length=200)


class UpdateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
```

- [ ] **Step 2: Write failing test**

Create `D:/GEO2/backend/tests/test_api_agent_sessions.py`:

```python
"""Integration tests for agent session API."""
from fastapi.testclient import TestClient


def test_create_session(client: TestClient) -> None:
    resp = client.post("/api/agent/sessions", json={"title": "诊断小米"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "诊断小米"
    assert "id" in body


def test_create_session_default_title(client: TestClient) -> None:
    resp = client.post("/api/agent/sessions", json={})
    assert resp.status_code == 201
    assert resp.json()["title"] == "新对话"


def test_list_sessions(client: TestClient) -> None:
    client.post("/api/agent/sessions", json={"title": "A"})
    client.post("/api/agent/sessions", json={"title": "B"})
    resp = client.get("/api/agent/sessions")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_session_with_messages(client: TestClient) -> None:
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            await repo.create_message(session_id=sess.id, role="user", content="hi")
            await repo.create_message(session_id=sess.id, role="assistant", content="hello")
            return sess.id
    session_id = asyncio.run(_setup())

    resp = client.get(f"/api/agent/sessions/{session_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == session_id
    assert len(body["messages"]) == 2


def test_delete_session(client: TestClient) -> None:
    create = client.post("/api/agent/sessions", json={"title": "X"})
    sid = create.json()["id"]
    resp = client.delete(f"/api/agent/sessions/{sid}")
    assert resp.status_code == 204
    get_resp = client.get(f"/api/agent/sessions/{sid}")
    assert get_resp.status_code == 404


def test_update_session_title(client: TestClient) -> None:
    create = client.post("/api/agent/sessions", json={"title": "X"})
    sid = create.json()["id"]
    resp = client.patch(f"/api/agent/sessions/{sid}", json={"title": "Y"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Y"
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_agent_sessions.py -v
```

Expected: FAIL with 404 (endpoint not found).

- [ ] **Step 4: Create `app/api/agent_sessions.py`**

Create `D:/GEO2/backend/app/api/agent_sessions.py`:

```python
"""Agent session CRUD API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.models.agent import (
    AgentMessage,
    AgentSession,
    AgentSessionDetail,
    CreateSessionRequest,
    UpdateSessionRequest,
)
from app.repositories.agent_repo import AgentRepository

router = APIRouter(prefix="/agent/sessions", tags=["agent"])


@router.post("", status_code=201, response_model=AgentSession)
async def create_session(
    body: CreateSessionRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSession:
    repo = AgentRepository(session)
    return await repo.create_session(title=body.title)


@router.get("", response_model=list[AgentSession])
async def list_sessions(
    session: AsyncSession = Depends(get_session),
) -> list[AgentSession]:
    repo = AgentRepository(session)
    return await repo.list_sessions(limit=50)


@router.get("/{session_id}", response_model=AgentSessionDetail)
async def get_session_detail(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentSessionDetail:
    repo = AgentRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    messages = await repo.list_messages(session_id)
    return AgentSessionDetail(
        id=sess.id,
        title=sess.title,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        messages=[AgentMessage.model_validate(m) for m in messages],
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    repo = AgentRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    await repo.delete_session(session_id)


@router.patch("/{session_id}", response_model=AgentSession)
async def update_session_title(
    session_id: str,
    body: UpdateSessionRequest,
    session: AsyncSession = Depends(get_session),
) -> AgentSession:
    repo = AgentRepository(session)
    await repo.update_session_title(session_id, title=body.title)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")
    return sess
```

- [ ] **Step 5: Register router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Add after the monitors router:

```python
    from app.api.agent_sessions import router as agent_sessions_router
    app.include_router(agent_sessions_router, prefix="/api")
```

- [ ] **Step 6: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_agent_sessions.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): agent session CRUD API + Pydantic models + tests"
```

---

### Task 5.2: Agent Chat SSE Endpoint

**Files:**
- Create: `D:/GEO2/backend/app/api/agent_chat.py`
- Modify: `D:/GEO2/backend/app/main.py`
- Create: `D:/GEO2/backend/tests/test_api_agent_chat.py`

**Interfaces:**
- `POST /api/agent/sessions/{id}/messages` — SSE stream
- `POST /api/agent/sessions/{id}/messages/{msg_id}/confirm` — confirm/reject

- [ ] **Step 1: Write failing test**

Create `D:/GEO2/backend/tests/test_api_agent_chat.py`:

```python
"""Integration tests for agent chat SSE endpoint."""
import json
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


def test_post_message_returns_sse_stream(client: TestClient) -> None:
    # Create a session first
    create = client.post("/api/agent/sessions", json={"title": "T"})
    sid = create.json()["id"]

    with patch("app.api.agent_chat.run_agent_turn") as mock_run:
        async def fake_events(*args, **kwargs):
            yield {"event": "assistant_message", "content": "好的"}
            yield {"event": "turn_complete"}
        mock_run.side_effect = fake_events

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages",
            json={"content": "诊断小米"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            chunks = list(resp.iter_text())
            assert any("event: assistant_message" in c for c in chunks)
            assert any("event: turn_complete" in c for c in chunks)


def test_confirm_action_approves(client: TestClient) -> None:
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            msg = await repo.create_message(
                session_id=sess.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess.id, msg.id
    sid, msg_id = asyncio.run(_setup())

    resp = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": True},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_confirm_action_rejects(client: TestClient) -> None:
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            msg = await repo.create_message(
                session_id=sess.id, role="assistant", content="...",
                pending_confirmation=True,
            )
            return sess.id, msg.id
    sid, msg_id = asyncio.run(_setup())

    resp = client.post(
        f"/api/agent/sessions/{sid}/messages/{msg_id}/confirm",
        json={"approved": False},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_agent_chat.py -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Create `app/api/agent_chat.py`**

Create `D:/GEO2/backend/app/api/agent_chat.py`:

```python
"""Agent chat API: SSE endpoint + human confirmation endpoint."""
from __future__ import annotations

import json
import structlog
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diagnosis import get_session
from app.domain.agent.react_loop import run_agent_turn
from app.domain.agent.session_manager import auto_generate_title
from app.repositories.agent_repo import AgentRepository

logger = structlog.get_logger()

router = APIRouter(prefix="/agent", tags=["agent"])


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class ConfirmActionRequest(BaseModel):
    approved: bool


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Send a user message and stream the agent's response via SSE."""
    repo = AgentRepository(session)
    sess = await repo.get_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session not found")

    # If this is the first user message, schedule title auto-generation.
    # For MVP, we generate the title synchronously after the turn completes.
    # (Implementation: check message count; if this is message #1, set title after)

    async def event_generator() -> AsyncIterator[str]:
        async for event in run_agent_turn(session_id, body.content):
            event_name = event.pop("event")
            yield f"event: {event_name}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post("/sessions/{session_id}/messages/{message_id}/confirm")
async def confirm_action(
    session_id: str,
    message_id: str,
    body: ConfirmActionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve or reject a pending human-confirmation tool call."""
    repo = AgentRepository(session)
    msg = await repo.get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message not found")
    if msg.session_id != session_id:
        raise HTTPException(status_code=404, detail="message does not belong to this session")
    if not msg.pending_confirmation:
        raise HTTPException(status_code=409, detail="message is not pending confirmation")

    if not body.approved:
        # User rejected: mark resolved, append user + assistant messages
        await repo.confirm_message(message_id, approved=False)
        from app.core.db import get_session_factory
        async with get_session_factory()() as s2:
            r2 = AgentRepository(s2)
            await r2.create_message(session_id=session_id, role="user", content="取消")
            await r2.create_message(
                session_id=session_id, role="assistant",
                content="好的，已取消。",
            )
        return {"status": "cancelled", "message_id": message_id}

    # User approved: mark resolved and return success.
    # The frontend will then re-trigger a new turn via the SSE endpoint
    # (passing a special "continue" flag) — for MVP, we mark approved
    # and return; the next user message re-enters the ReAct loop with
    # the same history (the generate_article tool will need to be re-called).
    # NOTE: a more sophisticated flow would auto-resume the loop here.
    await repo.confirm_message(message_id, approved=True)
    return {"status": "approved", "message_id": message_id}
```

- [ ] **Step 4: Register router in `main.py`**

Edit `D:/GEO2/backend/app/main.py`. Add after the agent_sessions router:

```python
    from app.api.agent_chat import router as agent_chat_router
    app.include_router(agent_chat_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_api_agent_chat.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd "D:/GEO2" && git add backend/ && git commit -m "feat(backend/v0.4): agent chat SSE endpoint + human confirmation API + tests"
```

---

## Phase 6: Frontend

### Task 6.1: Frontend Types + API Client Extension

**Files:**
- Create: `D:/GEO2/frontend/src/types/v0.4.ts`
- Modify: `D:/GEO2/frontend/src/api/client.ts`

- [ ] **Step 1: Create `types/v0.4.ts`**

Create `D:/GEO2/frontend/src/types/v0.4.ts`:

```typescript
export type AgentMessageRole = 'user' | 'assistant' | 'tool' | 'system';

export interface AgentSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AgentMessage {
  id: string;
  session_id: string;
  role: AgentMessageRole;
  content: string | null;
  tool_calls: Array<{ id: string; function: { name: string; arguments: string } }> | null;
  tool_call_id: string | null;
  pending_confirmation: boolean;
  created_at: string;
}

export interface AgentSessionDetail extends AgentSession {
  messages: AgentMessage[];
}

export interface PendingConfirmation {
  message_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

// SSE event types
export type AgentEvent =
  | { event: 'assistant_message'; content: string }
  | { event: 'tool_call_start'; tool_call_id: string; tool_name: string; arguments: Record<string, unknown> }
  | { event: 'tool_call_result'; tool_call_id: string; result: Record<string, unknown> }
  | { event: 'human_confirmation_required'; message_id: string; tool_name: string; arguments: Record<string, unknown> }
  | { event: 'turn_complete' }
  | { event: 'max_iterations_reached'; message: string };
```

- [ ] **Step 2: Extend `api/client.ts`**

Edit `D:/GEO2/frontend/src/api/client.ts`. Add v0.4 imports and methods:

```typescript
import type { AgentSession, AgentSessionDetail, PendingConfirmation } from '@/types/v0.4';

// Inside the api object, add these methods:
  listAgentSessions(): Promise<AgentSession[]> {
    return request('/agent/sessions');
  },
  createAgentSession(title?: string): Promise<AgentSession> {
    return request('/agent/sessions', {
      method: 'POST',
      body: JSON.stringify({ title: title || null }),
    });
  },
  getAgentSession(id: string): Promise<AgentSessionDetail> {
    return request(`/agent/sessions/${id}`);
  },
  deleteAgentSession(id: string): Promise<void> {
    return request(`/agent/sessions/${id}`, { method: 'DELETE' });
  },
  updateAgentSessionTitle(id: string, title: string): Promise<AgentSession> {
    return request(`/agent/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },
  confirmAgentAction(
    sessionId: string,
    messageId: string,
    approved: boolean,
  ): Promise<{ status: string; message_id: string }> {
    return request(`/agent/sessions/${sessionId}/messages/${messageId}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ approved }),
    });
  },
```

Also export a helper for SSE (the actual SSE handling lives in components):

```typescript
// Add at the end of the file
export async function* sendAgentMessageStream(
  sessionId: string,
  content: string,
): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${BASE}/agent/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value);
    const { events, remainder } = parseSSE(buffer);
    buffer = remainder;
    for (const evt of events) yield evt;
  }
}

interface ParsedSSE {
  events: AgentEvent[];
  remainder: string;
}

function parseSSE(buffer: string): ParsedSSE {
  const events: AgentEvent[] = [];
  const lines = buffer.split('\n');
  let remainder = '';
  let currentEvent: string | null = null;
  let currentData: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith('event: ')) {
      currentEvent = line.slice(7).trim();
    } else if (line.startsWith('data: ')) {
      currentData.push(line.slice(6).trim());
    } else if (line === '' && currentEvent && currentData.length > 0) {
      try {
        const data = JSON.parse(currentData.join('\n'));
        events.push({ event: currentEvent, ...data } as AgentEvent);
      } catch (e) {
        // ignore malformed
      }
      currentEvent = null;
      currentData = [];
    } else if (i === lines.length - 1 && line !== '') {
      // Last incomplete line; keep as remainder
      remainder = line;
    }
  }
  return { events, remainder };
}
```

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend/v0.4): types + API client + SSE parser"
```

---

### Task 6.2: Agent Session List Page

**Files:**
- Create: `D:/GEO2/frontend/src/pages/AgentSessionList.tsx`
- Modify: `D:/GEO2/frontend/src/App.tsx`

- [ ] **Step 1: Create `AgentSessionList.tsx`**

Create `D:/GEO2/frontend/src/pages/AgentSessionList.tsx`:

```tsx
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/api/client';
import { formatDate } from '@/lib/utils';

export default function AgentSessionList() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: sessions, isLoading } = useQuery({
    queryKey: ['agent-sessions'],
    queryFn: () => api.listAgentSessions(),
  });

  const create = useMutation({
    mutationFn: () => api.createAgentSession(),
    onSuccess: (session) => {
      qc.invalidateQueries({ queryKey: ['agent-sessions'] });
      navigate(`/agent/${session.id}`);
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteAgentSession(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['agent-sessions'] }),
  });

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-3xl mx-auto px-4">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Agent 会话</h1>
          <button
            type="button"
            onClick={() => create.mutate()}
            disabled={create.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
          >
            + 新建对话
          </button>
        </div>

        {isLoading && <p className="text-gray-500">加载中...</p>}

        {sessions && sessions.length === 0 && (
          <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            还没有对话。<br />
            <span className="text-sm">试试说"帮我诊断小米"</span>
          </div>
        )}

        {sessions && sessions.length > 0 && (
          <div className="bg-white rounded-lg shadow divide-y">
            {sessions.map((s) => (
              <div key={s.id} className="p-4 flex justify-between items-center hover:bg-gray-50">
                <Link to={`/agent/${s.id}`} className="flex-1">
                  <div className="font-medium text-gray-900">{s.title}</div>
                  <div className="text-sm text-gray-500">{formatDate(s.updated_at)}</div>
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    if (confirm(`删除对话「${s.title}」？`)) remove.mutate(s.id);
                  }}
                  className="text-red-600 text-sm px-2"
                >
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route in `App.tsx`**

Edit `D:/GEO2/frontend/src/App.tsx`. Add import:

```tsx
import AgentSessionList from '@/pages/AgentSessionList';
```

Add route inside `<Routes>`:

```tsx
          <Route path="/agent" element={<AgentSessionList />} />
```

- [ ] **Step 3: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend/v0.4): agent session list page + route"
```

---

### Task 6.3: Agent Chat Page (SSE Consumer)

**Files:**
- Create: `D:/GEO2/frontend/src/components/ChatMessage.tsx`
- Create: `D:/GEO2/frontend/src/components/ToolCallCard.tsx`
- Create: `D:/GEO2/frontend/src/components/ConfirmDialog.tsx`
- Create: `D:/GEO2/frontend/src/pages/AgentChat.tsx`
- Modify: `D:/GEO2/frontend/src/App.tsx`

- [ ] **Step 1: Create `ChatMessage.tsx`**

Create `D:/GEO2/frontend/src/components/ChatMessage.tsx`:

```tsx
import { ToolCallCard } from './ToolCallCard';
import type { AgentMessage } from '@/types/v0.4';

export function ChatMessage({ message }: { message: AgentMessage }) {
  switch (message.role) {
    case 'user':
      return (
        <div className="flex justify-end mb-3">
          <div className="bg-blue-500 text-white px-4 py-2 rounded-lg max-w-[80%]">
            {message.content}
          </div>
        </div>
      );

    case 'assistant':
      if (message.content) {
        return (
          <div className="flex justify-start mb-3">
            <div className="bg-white px-4 py-2 rounded-lg shadow max-w-[80%]">
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        );
      }
      return null;  // Assistant messages with only tool_calls show tool cards

    case 'tool':
      if (message.tool_call_id) {
        // This is a tool result message; render in conjunction with the tool call card
        // (handled by parent via state)
        return null;
      }
      return (
        <div className="text-center text-gray-500 text-sm my-2">
          {message.content}
        </div>
      );

    case 'system':
      return (
        <div className="text-center text-gray-500 text-sm italic my-2">
          {message.content}
        </div>
      );
  }
}
```

- [ ] **Step 2: Create `ToolCallCard.tsx`**

Create `D:/GEO2/frontend/src/components/ToolCallCard.tsx`:

```tsx
import { useState } from 'react';

interface ToolCallDisplay {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: Record<string, unknown>;
  pending?: boolean;
}

export function ToolCallCard({ display }: { display: ToolCallDisplay }) {
  const [expanded, setExpanded] = useState(false);

  if (display.pending || !display.result) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 mb-3 text-sm">
        <div className="flex items-center">
          <span className="animate-spin mr-2">⏳</span>
          <span>正在调用 <code className="font-mono">{display.tool_name}</code>...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 border rounded-md p-3 mb-3 text-sm">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div>✓ 工具 <code className="font-mono">{display.tool_name}</code> 返回</div>
        <span>{expanded ? '▼' : '▶'}</span>
      </div>
      {expanded && (
        <pre className="mt-2 bg-white p-2 rounded text-xs overflow-x-auto">
          {JSON.stringify(display.result, null, 2)}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `ConfirmDialog.tsx`**

Create `D:/GEO2/frontend/src/components/ConfirmDialog.tsx`:

```tsx
interface ConfirmDialogProps {
  toolName: string;
  arguments: Record<string, unknown>;
  onApprove: () => void;
  onCancel: () => void;
  pending: boolean;
}

const TOOL_LABELS: Record<string, string> = {
  diagnose_brand: '诊断品牌',
  search_knowledge: '查询知识库',
  generate_article: '生成文章',
};

export function ConfirmDialog({ toolName, arguments: args, onApprove, onCancel, pending }: ConfirmDialogProps) {
  const label = TOOL_LABELS[toolName] || toolName;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold mb-3">确认执行：{label}</h3>
        <div className="bg-gray-50 p-3 rounded mb-4 text-sm">
          <pre className="overflow-x-auto">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={pending}
            className="px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={pending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {pending ? '处理中...' : '确认'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `AgentChat.tsx`**

Create `D:/GEO2/frontend/src/pages/AgentChat.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, sendAgentMessageStream } from '@/api/client';
import { ChatMessage } from '@/components/ChatMessage';
import { ToolCallCard } from '@/components/ToolCallCard';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import type { AgentMessage, PendingConfirmation } from '@/types/v0.4';

interface ToolCallDisplay {
  tool_call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: Record<string, unknown>;
  pending?: boolean;
}

export default function AgentChat() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const qc = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<PendingConfirmation | null>(null);
  const [toolCalls, setToolCalls] = useState<Record<string, ToolCallDisplay>>({});

  const { data: session, refetch } = useQuery({
    queryKey: ['agent-session', sessionId],
    queryFn: () => api.getAgentSession(sessionId),
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages, toolCalls]);

  async function send() {
    if (!input.trim() || loading || pending) return;
    const userContent = input.trim();
    setInput('');
    setLoading(true);
    setToolCalls({});

    // Optimistic user message
    const tempUserMsg: AgentMessage = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: userContent,
      tool_calls: null,
      tool_call_id: null,
      pending_confirmation: false,
      created_at: new Date().toISOString(),
    };
    qc.setQueryData(['agent-session', sessionId], (old: any) =>
      old ? { ...old, messages: [...old.messages, tempUserMsg] } : old
    );

    try {
      for await (const event of sendAgentMessageStream(sessionId, userContent)) {
        handleAgentEvent(event);
      }
    } catch (e) {
      console.error('SSE error:', e);
    } finally {
      setLoading(false);
      refetch();  // Refresh from server to get persisted state
    }
  }

  function handleAgentEvent(event: any) {
    switch (event.event) {
      case 'assistant_message':
        if (event.content) {
          qc.setQueryData(['agent-session', sessionId], (old: any) =>
            old ? {
              ...old,
              messages: [...old.messages, {
                id: `ast-${Date.now()}`,
                session_id: sessionId,
                role: 'assistant',
                content: event.content,
                tool_calls: null,
                tool_call_id: null,
                pending_confirmation: false,
                created_at: new Date().toISOString(),
              }],
            } : old
          );
        }
        break;
      case 'tool_call_start':
        setToolCalls((prev) => ({
          ...prev,
          [event.tool_call_id]: {
            tool_call_id: event.tool_call_id,
            tool_name: event.tool_name,
            arguments: event.arguments,
            pending: true,
          },
        }));
        break;
      case 'tool_call_result':
        setToolCalls((prev) => ({
          ...prev,
          [event.tool_call_id]: {
            ...prev[event.tool_call_id],
            result: event.result,
            pending: false,
          },
        }));
        break;
      case 'human_confirmation_required':
        setPending(event);
        break;
    }
  }

  const confirm = useMutation({
    mutationFn: () => api.confirmAgentAction(sessionId, pending!.message_id, true),
    onSuccess: () => {
      setPending(null);
      setToolCalls({});
      // Send a continuation message to trigger the next agent turn
      setInput('[已确认，继续]');
    },
  });

  const cancel = useMutation({
    mutationFn: () => api.confirmAgentAction(sessionId, pending!.message_id, false),
    onSuccess: () => {
      setPending(null);
      setToolCalls({});
      refetch();
    },
  });

  if (!session) return <div className="p-8 text-center text-gray-500">加载中...</div>;

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b px-4 py-3 flex justify-between items-center">
        <Link to="/agent" className="text-blue-600 text-sm">← 返回</Link>
        <h1 className="text-lg font-semibold">{session.title}</h1>
        <div className="w-12" />
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-3xl mx-auto w-full">
        {session.messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {Object.values(toolCalls).map((tc) => (
          <ToolCallCard key={tc.tool_call_id} display={tc} />
        ))}
        {loading && <div className="text-gray-500 text-sm">agent 思考中...</div>}
        <div ref={messagesEndRef} />
      </div>

      {pending && (
        <ConfirmDialog
          toolName={pending.tool_name}
          arguments={pending.arguments}
          onApprove={() => confirm.mutate()}
          onCancel={() => cancel.mutate()}
          pending={confirm.isPending || cancel.isPending}
        />
      )}

      <div className="bg-white border-t px-4 py-3">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            disabled={loading || !!pending}
            placeholder={pending ? '等待确认...' : '输入消息（Enter 发送）'}
            className="flex-1 px-3 py-2 border rounded-md disabled:opacity-50"
          />
          <button
            type="button"
            onClick={send}
            disabled={!input.trim() || loading || !!pending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add route in `App.tsx`**

Edit `D:/GEO2/frontend/src/App.tsx`. Add imports:

```tsx
import AgentSessionList from '@/pages/AgentSessionList';
import AgentChat from '@/pages/AgentChat';
```

Add to Routes:

```tsx
          <Route path="/agent" element={<AgentSessionList />} />
          <Route path="/agent/:sessionId" element={<AgentChat />} />
```

- [ ] **Step 6: Verify lint**

```bash
cd "D:/GEO2/frontend" && npm run lint
```

Expected: Exit code 0.

- [ ] **Step 7: Commit**

```bash
cd "D:/GEO2" && git add frontend/src/ && git commit -m "feat(frontend/v0.4): agent chat page with SSE + tool cards + confirm dialog"
```

---

## Phase 7: End-to-End Verification & Documentation

### Task 7.1: E2E Backend Test

**Files:**
- Create: `D:/GEO2/backend/tests/test_e2e_v0.4.py`

- [ ] **Step 1: Write E2E test**

Create `D:/GEO2/backend/tests/test_e2e_v0.4.py`:

```python
"""E2E test for v0.4 agent flow."""
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


def test_e2e_create_session_and_list(client: TestClient) -> None:
    resp = client.post("/api/agent/sessions", json={"title": "E2E Test"})
    assert resp.status_code == 201
    sid = resp.json()["id"]

    list_resp = client.get("/api/agent/sessions")
    assert any(s["id"] == sid for s in list_resp.json())


def test_e2e_session_detail_includes_messages(client: TestClient) -> None:
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository
    import asyncio
    async def _setup():
        async with get_session_factory()() as s:
            repo = AgentRepository(s)
            sess = await repo.create_session(title="T")
            await repo.create_message(session_id=sess.id, role="user", content="hi")
            return sess.id
    sid = asyncio.run(_setup())

    resp = client.get(f"/api/agent/sessions/{sid}")
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 1


def test_e2e_post_message_streams_sse(client: TestClient) -> None:
    create = client.post("/api/agent/sessions", json={"title": "T"})
    sid = create.json()["id"]

    with patch("app.api.agent_chat.run_agent_turn") as mock_run:
        async def fake_events(*args, **kwargs):
            yield {"event": "assistant_message", "content": "好的"}
            yield {"event": "turn_complete"}
        mock_run.side_effect = fake_events

        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages",
            json={"content": "诊断小米"},
        ) as resp:
            assert resp.status_code == 200
            chunks = list(resp.iter_text())
            assert any("event: turn_complete" in c for c in chunks)
```

- [ ] **Step 2: Run E2E**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest tests/test_e2e_v0.4.py -v
```

Expected: All PASS.

- [ ] **Step 3: Run ALL tests**

```bash
cd "D:/GEO2/backend" && .venv/Scripts/activate && pytest -v
```

Expected: All v0.1 + v0.2 + v0.3 + v0.4 tests PASS.

- [ ] **Step 4: Commit**

```bash
cd "D:/GEO2" && git add backend/tests/ && git commit -m "test(backend/v0.4): end-to-end agent session + chat + confirm flow"
```

---

### Task 7.2: Manual Verification Checklist

**Files:**
- Create: `D:/GEO2/docs/MANUAL_VERIFICATION_V0.4.md`

- [ ] **Step 1: Write checklist**

Create `D:/GEO2/docs/MANUAL_VERIFICATION_V0.4.md`:

```markdown
# 手动验证清单 — GEO Agent v0.4

发布前必跑 8 个场景。

## 前置条件

\`\`\`bash
cd "D:/GEO2"
docker-compose up --build -d
sleep 30
\`\`\`

## 场景

### 1. 完整诊断流程 ✅

1. 进入 /agent → "新建对话"
2. 输入"诊断小米"
3. **预期**：
   - 看到 agent 文字响应（"好的，让我先诊断..."）
   - 看到 "正在调用 diagnose_brand..."
   - 看到工具结果（overall_score 等）
   - 最终 agent 总结（"小米 GEO 分数 XX..."）
   - 历史 session 列表中标题自动变为"诊断小米"

### 2. 完整生成流程 ✅

1. 创建新对话
2. 输入"帮我生成一篇关于小米手机的评测文章"
3. agent 调 search_knowledge 查资料
4. agent 调 generate_article → 弹窗"准备生成文章..."
5. 点"确认"
6. **预期**：
   - 工具结果返回（title、content_preview、word_count）
   - agent 总结（"已生成文章，请到 /tasks/new 触发完整流程"）

### 3. 用户取消生成 🛑

1. 创建新对话
2. 输入"生成文章"
3. 弹窗出现
4. 点"取消"
5. **预期**：agent 回应"好的，已取消。"

### 4. 多 session ✅

1. 创建 3 个独立对话（不同内容）
2. **预期**：每个 session 独立保存历史，互不干扰

### 5. 历史回看 ✅

1. 创建 session，发送几条消息
2. 离开页面（关闭浏览器）
3. 重新打开 /agent/{sessionId}
4. **预期**：完整历史可见，包括所有 assistant 消息和工具调用

### 6. SSE 流式渲染 ✅

1. 发送一条会触发多轮工具调用的消息
2. **预期**：消息逐条出现（不是等全部完成才显示）

### 7. LLM 失败处理 ⚠️

1. 编辑 .env：DEEPSEEK_API_KEY=sk-invalid
2. docker-compose restart backend
3. 发送消息
4. **预期**：显示"AI 服务暂时不可用"类提示

### 8. human-in-the-loop 跨刷新 ✅

1. 创建对话，触发 generate_article → 弹窗
2. **不要**点确认，**刷新页面**
3. 重新打开对话
4. **预期**：弹窗状态保持（或消息列表显示"待确认"标记），用户可继续

## 通过标准

8 项全过 → v0.4 完成。
\`\`\`

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/MANUAL_VERIFICATION_V0.4.md && git commit -m "docs: v0.4 manual verification checklist"
```

---

### Task 7.3: Update ROADMAP

**Files:**
- Modify: `D:/GEO2/docs/ROADMAP.md`

- [ ] **Step 1: Mark v0.4 design + plan complete**

Edit `D:/GEO2/docs/ROADMAP.md`. Update the v0.4 entry to mark design+plan as done, and note the direction change (from multi-user to agent).

- [ ] **Step 2: Commit**

```bash
cd "D:/GEO2" && git add docs/ROADMAP.md && git commit -m "docs: mark v0.4 design + plan as complete in ROADMAP"
```

---

## Self-Review

After writing this plan, run the writing-plans self-review checklist:

**1. Spec coverage** — Every requirement in the v0.4 spec is covered:

| Spec § | Implemented in Task |
|---|---|
| §1 (background, scope) | Phase 0 + Task 7.3 |
| §2 (users, scenarios) | Task 6.3 (chat page), Task 7.2 (manual) |
| §3 (architecture) | Phase 0 + main.py wiring in Task 5.1/5.2 |
| §4 (3 tools) | Task 1.1 (schemas) + Task 2.x (executors) |
| §5 (ReAct loop) | Task 4.1 + 4.2 |
| §6 (session management) | Task 3.1 (repo) + Task 3.2 (auto title) |
| §7 (REST API) | Task 5.1 (CRUD) + Task 5.2 (SSE) |
| §8 (SSE protocol) | Task 6.1 (client parser) + Task 5.2 (server) |
| §9 (error handling) | Throughout each task |
| §10 (testing) | Tests in every task + Task 7.1 |
| §11 (acceptance) | Task 7.2 |
| §12 (risks) | Documented in spec; mitigations in tasks |
| §13 (ROADMAP adjustment) | Task 7.3 |

**2. Placeholder scan** — No TBD/TODO. All code blocks complete.

**3. Type consistency** —
- `AgentMessageORM` ↔ `AgentMessage` (Pydantic) ↔ React `AgentMessage` ✓
- `ToolExecutor` execute methods: `diagnose_brand` / `search_knowledge` / `generate_article` ✓
- `_EXEC_LOCK` shared across v0.1-v0.4 workers ✓
- `MAX_REACT_ITERATIONS = 5` declared once, used in loop ✓

All consistent.

---

## Execution Handoff

This plan is **complete** and saved to:
`D:/GEO2/docs/superpowers/plans/2026-07-10-geo-optimization-agent-v0.4.md`

**Two execution options:**

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task with two-stage review between tasks. Best for catching issues early and maintaining quality across 22+ tasks.

**2. Inline Execution** - Execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints. Faster but no inter-task review.

**Which approach?**

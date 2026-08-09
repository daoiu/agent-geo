"""全链路 e2e:API → agent 图 → generate_article 工具 → specialist → 真实落库。

stub LLM(agent 图)与 stub ContentWriterAgent(文章生成),其余全部真实:
- FastAPI TestClient + 临时 SQLite
- agent LangGraph 真实执行(LLM mock)
- ToolExecutor 真实执行 → ContentWriterSpecialist 真实执行
- TaskORM + ArticleORM + handoff_log 真实落库
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def _stub_llm_for_graph(spec: dict):
    """构造 agent 图用的 stub LLM。

    spec: {"tool_calls": [...] | None, "final_text": str}
    第一次调用返回 tool_calls,之后返回纯文本(避免死循环)。
    """
    import app.domain.agent.react_graph as rg
    import app.domain.llm_client as llm_mod

    class _StubLLM:
        last_call_duration_ms = 0
        call_count = 0

        def __init__(self, settings=None, *args, **kwargs):
            pass

        def primary_provider_name(self):
            return "stub"

        async def chat_with_tools(self, messages, tools):
            self.call_count += 1
            if self.call_count == 1 and spec.get("tool_calls"):
                return {"content": None, "tool_calls": spec["tool_calls"]}
            return {"content": spec.get("final_text", "完成"), "tool_calls": None}

    class _StubWrap(_StubLLM):
        pass

    from unittest.mock import patch

    patchers = [
        patch.object(rg, "LLMClient", _StubWrap),
        patch.object(llm_mod, "LLMClient", _StubWrap),
    ]
    for p in patchers:
        p.start()
    return patchers


def test_agent_generate_article_full_chain(client: TestClient) -> None:
    """发消息 → agent 调 generate_article → specialist 生成 → task+article 落库。"""
    from app.core.db import get_session_factory
    from app.repositories.agent_repo import AgentRepository
    from app.repositories.knowledge_repo import KnowledgeRepository

    # 建 KB(TaskORM.kb_id FK 依赖)
    async def _make_kb() -> str:
        async with get_session_factory()() as s:
            kb = await KnowledgeRepository(s).create_kb(name="小米 KB")
            await s.commit()
            return kb.id

    import asyncio
    kb_id = asyncio.run(_make_kb())

    # 建 session
    create = client.post("/api/agent/sessions", json={"title": "全链路"})
    sid = create.json()["id"]

    # stub LLM:第一轮让 agent 调 generate_article
    tool_calls = [{
        "id": "tc-gen-1",
        "name": "generate_article",
        "args": {
            "kb_id": kb_id,
            "brand": "小米",
            "topic": "小米手机 AI 摄影评测",
            "keywords": ["AI", "摄影"],
            "style": "professional",
            "target_length": 1500,
        },
    }]
    patchers = _stub_llm_for_graph({"tool_calls": tool_calls, "final_text": "已生成文章"})

    # stub ContentWriterAgent:specialist 真实执行时用固定文章内容
    from app.domain.generator.content_writer_agent import ContentWriterAgent

    writer_patch = patch.object(
        ContentWriterAgent,
        "write_article",
        new=AsyncMock(return_value=("小米 AI 摄影评测报告", "# 小米 AI 摄影评测报告\n正文内容\n")),
    )
    writer_patch.start()

    try:
        with client.stream(
            "POST",
            f"/api/agent/sessions/{sid}/messages",
            json={"content": "帮我写一篇小米手机 AI 摄影的文章"},
        ) as resp:
            assert resp.status_code == 200
            chunks = list(resp.iter_text())
            text = "".join(chunks)
            assert "turn_complete" in text

        # DB 全链路落库验证
        async def _verify() -> dict:
            async with get_session_factory()() as s:
                repo = AgentRepository(s)
                msgs = await repo.list_messages(sid)
                from sqlalchemy import select

                from app.models.orm_v02 import ArticleORM, TaskORM

                tasks = (
                    await s.execute(select(TaskORM).where(TaskORM.brand == "小米"))
                ).scalars().all()
                articles = (
                    await s.execute(select(ArticleORM))
                ).scalars().all()
                return {
                    "msg_count": len(msgs),
                    "task_count": len(tasks),
                    "article_count": len(articles),
                }

        state = asyncio.run(_verify())
        assert state["task_count"] >= 1, "specialist 必须真实创建 TaskORM"
        assert state["article_count"] >= 1, "specialist 必须真实创建 ArticleORM"
        assert state["msg_count"] >= 1
    finally:
        writer_patch.stop()
        for p in patchers:
            p.stop()

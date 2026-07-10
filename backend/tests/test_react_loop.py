"""Tests for ReAct loop (v0.4)."""
from __future__ import annotations

import json

import pytest

from app.domain.agent.react_loop import build_messages


def test_build_messages_starts_with_system_prompt() -> None:
    """第一条是 system prompt。"""
    messages = build_messages(history=[])
    assert messages[0]["role"] == "system"
    assert "GEO" in messages[0]["content"]


def test_build_messages_passes_through_user() -> None:
    """user 消息直接传递。"""
    history = [{"role": "user", "content": "诊断小米"}]
    messages = build_messages(history=history)
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "诊断小米"


def test_build_messages_passes_through_assistant_text() -> None:
    """assistant 纯文本消息传递。"""
    history = [
        {"role": "user", "content": "诊断"},
        {"role": "assistant", "content": "好的，让我先看分数。"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    assert asst["content"] == "好的，让我先看分数。"
    assert "tool_calls" not in asst


def test_build_messages_converts_tool_role_messages() -> None:
    """'tool' role 消息 + tool_call_id 被正确转换（OpenAI 协议要求）。"""
    history = [
        {"role": "user", "content": "诊断"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "tc1", "function": {"name": "diagnose_brand", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "tc1", "content": "result"},
    ]
    messages = build_messages(history=history)
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "tc1"
    assert tool_msgs[0]["content"] == "result"


def test_build_messages_serializes_tool_call_arguments_from_json_string() -> None:
    """DB 存储的 tool_calls.arguments 是 JSON 字符串；LLM 需要对象。"""
    history = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {
                        "name": "diagnose_brand",
                        "arguments": '{"brand_name": "小米"}',
                    },
                }
            ],
        },
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, dict)
    assert args["brand_name"] == "小米"


def test_build_messages_passes_dict_arguments_unchanged() -> None:
    """如果 arguments 已经是 dict，直接用。"""
    history = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {
                        "name": "diagnose_brand",
                        "arguments": {"brand_name": "小米"},
                    },
                }
            ],
        },
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert args == {"brand_name": "小米"}


def test_build_messages_skips_unknown_role() -> None:
    """未知 role 消息被忽略（防御性）。"""
    history = [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "old system msg"},
    ]
    messages = build_messages(history=history)
    # 系统 prompt 在前；旧的 system 消息被忽略
    assert len(messages) == 2  # system + user
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


# ===========================================================================
# run_agent_turn integration tests
# ===========================================================================


class TestRunAgentTurn:
    @pytest.mark.asyncio
    async def test_diagnose_brand_flow(self, db_session) -> None:
        """用户输入'诊断小米' → agent 调 diagnose_brand → 返回总结。"""
        from unittest.mock import AsyncMock, patch

        from app.repositories.agent_repo import AgentRepository

        repo = AgentRepository(db_session)
        session = await repo.create_session(title="T")

        # LLM 第一次：返回 tool_call；第二次：返回 final text
        llm_responses = [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "tc1",
                        "function": {
                            "name": "diagnose_brand",
                            "arguments": '{"brand_name":"小米","industry":"手机","official_url":"https://www.mi.com"}',
                        },
                    }
                ],
            },
            {"content": "小米 GEO 分数 45，建议添加 Schema。", "tool_calls": None},
        ]

        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(side_effect=llm_responses)

            # ToolExecutor.execute 也需要 mock（避免触发真 v0.1）
            with patch(
                "app.domain.agent.tool_executor.ToolExecutor.execute",
                new=AsyncMock(return_value={
                    "report_id": "r1", "overall_score": 45, "mention_rate": 0.1,
                    "dimensions": {"authority": 5.0, "relevance": 3.0},
                    "suggestions_count": 1, "top_suggestion": "添加 Schema",
                }),
            ):
                from app.domain.agent.react_loop import run_agent_turn

                events = []
                async for evt in run_agent_turn(session.id, "诊断小米"):
                    events.append(evt)

        event_names = [e["event"] for e in events]
        assert "assistant_message" in event_names
        assert "tool_call_start" in event_names
        assert "tool_call_result" in event_names
        assert "turn_complete" in event_names

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self, db_session) -> None:
        """LLM 一直返回 tool_call，超过 MAX_REACT_ITERATIONS 后停止。"""
        from unittest.mock import AsyncMock, patch

        from app.repositories.agent_repo import AgentRepository

        repo = AgentRepository(db_session)
        session = await repo.create_session(title="T")

        # 一直返回 tool_call
        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(return_value={
                "content": None,
                "tool_calls": [
                    {
                        "id": "tc",
                        "function": {
                            "name": "diagnose_brand",
                            "arguments": '{"brand_name":"X","industry":"Y","official_url":"https://x.com"}',
                        },
                    }
                ],
            })
            with patch(
                "app.domain.agent.tool_executor.ToolExecutor.execute",
                new=AsyncMock(return_value={"x": 1}),
            ):
                from app.domain.agent.react_loop import run_agent_turn

                events = []
                async for evt in run_agent_turn(session.id, "X"):
                    events.append(evt)

        assert events[-1]["event"] == "max_iterations_reached"

    @pytest.mark.asyncio
    async def test_human_confirmation_pauses_loop(self, db_session) -> None:
        """写类工具抛 HumanConfirmationRequired → yield SSE 并暂停。"""
        from unittest.mock import AsyncMock, patch

        from app.repositories.agent_repo import AgentRepository

        repo = AgentRepository(db_session)
        session = await repo.create_session(title="T")

        # LLM 第一次：返回 generate_article tool_call
        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(return_value={
                "content": "我来生成文章。",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "function": {
                            "name": "generate_article",
                            "arguments": '{"kb_id":"kb1","brand":"小米","topic":"产品评测与体验","keywords":["性能"]}',
                        },
                    }
                ],
            })

            from app.domain.agent.react_loop import run_agent_turn

            events = []
            async for evt in run_agent_turn(session.id, "生成文章"):
                events.append(evt)

        event_names = [e["event"] for e in events]
        assert "assistant_message" in event_names
        assert "tool_call_start" in event_names
        assert "human_confirmation_required" in event_names

        # 必须有 human_confirmation_required 事件，附 message_id / tool_name / arguments
        hcr = next(e for e in events if e["event"] == "human_confirmation_required")
        assert hcr["message_id"] != ""
        assert hcr["tool_name"] == "generate_article"
        assert hcr["arguments"]["brand"] == "小米"

    @pytest.mark.asyncio
    async def test_run_agent_turn_persists_user_message(self, db_session) -> None:
        """run_agent_turn 会把 user 消息持久化。"""
        from unittest.mock import AsyncMock, patch

        from sqlalchemy import select

        from app.models.orm_v04 import AgentMessageORM
        from app.repositories.agent_repo import AgentRepository

        repo = AgentRepository(db_session)
        session = await repo.create_session(title="T")

        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(return_value={
                "content": "好的",
                "tool_calls": None,
            })

            from app.domain.agent.react_loop import run_agent_turn

            events = []
            async for evt in run_agent_turn(session.id, "用户的原始消息"):
                events.append(evt)

        result = await db_session.execute(
            select(AgentMessageORM).where(AgentMessageORM.session_id == session.id)
        )
        msgs = list(result.scalars().all())
        user_msgs = [m for m in msgs if m.role == "user"]
        assert any(m.content == "用户的原始消息" for m in user_msgs)


class TestRunAgentTurnFromCheckpoint:
    """断点续跑：confirm_action approved=True 后真正调 ContentWriter 并继续 ReAct。"""

    @pytest.mark.asyncio
    async def test_resume_calls_confirmed_executor_and_continues(
        self, db_session
    ) -> None:
        """从 checkpoint 续跑：调 _execute_generate_article_confirmed，再调 LLM。"""
        from unittest.mock import AsyncMock, patch

        from app.repositories.agent_repo import AgentRepository

        repo = AgentRepository(db_session)
        session = await repo.create_session(title="T")
        # 模拟已有 pending message（就像 generate_article 抛 HumanConfirmationRequired 后留下的）
        pending_msg = await repo.create_message(
            session_id=session.id,
            role="assistant",
            content="准备生成文章...",
            tool_calls=[
                {
                    "id": "tc-pending",
                    "tool": "generate_article",
                    "arguments": {
                        "kb_id": "kb1",
                        "brand": "小米",
                        "topic": "产品评测与体验",
                        "keywords": ["性能", "拍照"],
                    },
                }
            ],
            pending_confirmation=True,
        )

        # 把 message 标记为 pending_confirmation=1（前面已设置）
        # 续跑函数需要找到这个 pending message 并解析 arguments

        # Mock confirmed executor 返回预览
        confirmed_result = {
            "status": "generated",
            "title": "小米产品评测",
            "content_preview": "前 300 字符预览...",
            "word_count": 1500,
            "next_step": "如满意请到 /tasks/new",
        }

        # Mock LLM 续跑后返回最终总结
        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(return_value={
                "content": "已生成文章，请到任务列表审核。",
                "tool_calls": None,
            })

            with patch(
                "app.domain.agent.tool_executor.ToolExecutor._execute_generate_article_confirmed",
                new=AsyncMock(return_value=confirmed_result),
            ) as mock_confirmed:
                from app.domain.agent.react_loop import (
                    run_agent_turn_from_checkpoint,
                )

                events = []
                async for evt in run_agent_turn_from_checkpoint(
                    session.id, pending_msg.id
                ):
                    events.append(evt)

                mock_confirmed.assert_called_once()

        event_names = [e["event"] for e in events]
        assert "tool_call_result" in event_names
        assert "assistant_message" in event_names
        assert "turn_complete" in event_names
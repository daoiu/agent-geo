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


def test_build_messages_keeps_tool_call_arguments_as_json_string() -> None:
    """OpenAI 协议要求 tool_calls.arguments 是 JSON 字符串（不是对象）。

    DB 已存字符串，build_messages 必须原样透传给 LLM，不能 json.loads 成 dict，
    否则严格 provider 报 400 'Mismatch type string with value object'。
    """
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
        {"role": "tool", "tool_call_id": "tc1", "content": "ok"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, str)
    assert json.loads(args)["brand_name"] == "小米"


def test_build_messages_serializes_dict_arguments_to_json_string() -> None:
    """若 arguments 意外是 dict，序列化成 JSON 字符串再发给 LLM（协议要求字符串）。"""
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
        {"role": "tool", "tool_call_id": "tc1", "content": "ok"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, str)
    assert json.loads(args)["brand_name"] == "小米"


def test_build_messages_empty_args_stays_string_regression() -> None:
    """回归（v0.6 P1.4）：无参工具 list_knowledge_bases 的 arguments '{}' 必须保持
    JSON 字符串。曾因 build_messages json.loads 成对象 {} 触发 provider 400。"""
    history = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc1",
                    "function": {
                        "name": "list_knowledge_bases",
                        "arguments": "{}",
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tc1", "content": "{}"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    args = asst["tool_calls"][0]["function"]["arguments"]
    assert isinstance(args, str)
    assert args == "{}"


def test_build_messages_drops_dangling_tool_calls() -> None:
    """回归：assistant 声明了 tool_calls 但没有对应 tool 结果（HumanConfirmation /
    中断的流），必须丢弃该 tool_calls，否则 provider 报
    'tool call result does not follow tool call' 400。content 仍保留。"""
    history = [
        {"role": "user", "content": "生成一篇"},
        {
            "role": "assistant",
            "content": "准备生成文章：...",
            "tool_calls": [
                {"id": "dangling1", "function": {"name": "generate_article", "arguments": "{}"}}
            ],
        },
        {"role": "user", "content": "算了"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    assert "tool_calls" not in asst  # dangling 被丢弃
    assert asst["content"] == "准备生成文章：..."  # 文本保留


def test_build_messages_skips_orphan_tool_result() -> None:
    """孤儿 tool 结果（没有声明它的 assistant tool_call）被跳过，避免破坏配对。"""
    history = [
        {"role": "tool", "tool_call_id": "orphan", "content": "result"},
    ]
    messages = build_messages(history=history)
    assert all(m.get("role") != "tool" for m in messages)


def test_build_messages_keeps_only_resolved_tool_call_in_multi() -> None:
    """一条 assistant 有多个 tool_calls，只保留有结果的那个。"""
    history = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "a", "function": {"name": "list_knowledge_bases", "arguments": "{}"}},
                {"id": "b", "function": {"name": "list_knowledge_bases", "arguments": "{}"}},
            ],
        },
        {"role": "tool", "tool_call_id": "a", "content": "ra"},
    ]
    messages = build_messages(history=history)
    asst = next(m for m in messages if m["role"] == "assistant")
    ids = [tc["id"] for tc in asst["tool_calls"]]
    assert ids == ["a"]
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1


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
    async def test_generate_article_does_not_pause_loop(
        self, db_session
    ) -> None:
        """v0.6 P1.6+: generate_article 默认走后台（article_count=1），不再抛 HumanConfirmationRequired。

        agent turn 应该正常 yield tool_call_result → turn_complete，**不**出现
        human_confirmation_required 事件。
        """
        from unittest.mock import AsyncMock, patch

        from app.repositories.agent_repo import AgentRepository
        from app.repositories.knowledge_repo import KnowledgeRepository

        kb_repo = KnowledgeRepository(db_session)
        kb = await kb_repo.create_kb(name="KB")

        agent_repo = AgentRepository(db_session)
        agent_session = await agent_repo.create_session(title="T")

        # LLM 第一次：返回 generate_article tool_call；第二次：返回 final text
        llm_responses = [
            {
                "content": "我来生成文章。",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "function": {
                            "name": "generate_article",
                            "arguments": json.dumps({
                                "kb_id": kb.id,
                                "brand": "小米",
                                "topic": "产品评测与体验",
                                "keywords": ["性能", "拍照"],
                            }, ensure_ascii=False),
                        },
                    }
                ],
            },
            {"content": "已生成，请到 /tasks/<id> 审核。", "tool_calls": None},
        ]

        with patch("app.domain.agent.react_loop.LLMClient") as MockLLM:
            mock_instance = MockLLM.return_value
            mock_instance.chat_with_tools = AsyncMock(side_effect=llm_responses)
            # 防止后台 worker 真的跑
            with patch("app.tasks.task_worker.schedule_task"):
                from app.domain.agent.react_loop import run_agent_turn

                events = []
                async for evt in run_agent_turn(agent_session.id, "生成文章"):
                    events.append(evt)

        event_names = [e["event"] for e in events]
        assert "assistant_message" in event_names
        assert "tool_call_start" in event_names
        assert "tool_call_result" in event_names
        assert "turn_complete" in event_names
        # 关键回归：v0.6 P1.6+ 不再弹 human_confirmation
        assert "human_confirmation_required" not in event_names

        # tool_call_result 含 task_id（说明走后台）
        tcr = next(e for e in events if e["event"] == "tool_call_result")
        assert "task_id" in tcr["result"]
        assert tcr["result"]["article_count"] == 1

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

def test_phase3_settings_defaults():
    from app.core.config import Settings
    s = Settings(deepseek_api_key="x")
    assert s.context_window_messages == 40
    assert s.tool_result_max_chars == 2000
    assert s.tool_result_keep_recent == 3


# ============================================================================
# Phase 3 — build_messages 滑动窗口 + 旧 tool 结果截断
# ============================================================================


def test_build_messages_window_keeps_last_n():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    messages = build_messages(history, window_messages=3)
    assert messages[0]["role"] == "system"
    assert [m["content"] for m in messages[1:]] == ["m7", "m8", "m9"]


def test_build_messages_window_none_keeps_all():
    history = [{"role": "user", "content": f"m{i}"} for i in range(10)]
    messages = build_messages(history)
    assert len([m for m in messages if m["role"] == "user"]) == 10


def test_build_messages_window_drops_dangling_pair():
    history = [
        {"role": "user", "content": "老消息填充1"},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "tc1", "function": {"name": "x", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "tc1", "content": "result"},
        {"role": "user", "content": "新消息"},
    ]
    messages = build_messages(history, window_messages=2)
    assert all(m.get("role") != "tool" for m in messages)


def test_build_messages_truncates_old_tool_result():
    big = "x" * 5000
    history = [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "a", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": big},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "b", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "b", "content": "recent"},
    ]
    messages = build_messages(history, tool_result_max_chars=100,
                              tool_result_keep_recent=1)
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    a_msg = next(m for m in tool_msgs if m["tool_call_id"] == "a")
    b_msg = next(m for m in tool_msgs if m["tool_call_id"] == "b")
    assert a_msg["content"].endswith("…(truncated)")
    assert len(a_msg["content"]) <= 100 + len("…(truncated)")
    assert b_msg["content"] == "recent"


def test_build_messages_truncate_boundary_not_cut():
    exact = "y" * 100
    history = [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "a", "function": {"name": "t", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": exact},
    ]
    messages = build_messages(history, tool_result_max_chars=100,
                              tool_result_keep_recent=0)
    tool_msg = next(m for m in messages if m.get("role") == "tool")
    assert tool_msg["content"] == exact

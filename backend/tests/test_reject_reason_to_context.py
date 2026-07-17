"""验证 reject 理由进入 LLM 上下文（P1#26 / Task 27）。

行为契约：
- ConfirmActionRequest 新增可选 reason 字段
- approved=False + reason: 把 reason 写入 user 消息(而不是固定 "取消")
- LLM 下次 turn 能看到这条 user 消息(已通过 build_messages 历史)
- approved=True + reason: reason 忽略(approved 不需要 reason)
- 不传 reason 时保持向后兼容(写默认 "取消")
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.agent_repo import AgentRepository


def _setup_pending(db_session):
    """同步创建 session + pending message。"""
    async def _do():
        repo = AgentRepository(db_session)
        sess = await repo.create_session(title="T")
        msg = await repo.create_message(
            session_id=sess.id, role="assistant", content="...",
            pending_confirmation=True,
        )
        return sess.id, msg.id
    return asyncio.run(_do())


def _call_confirm_direct(sid, msg_id, payload):
    """直接调 confirm_action 函数(避开 client fixture 的 monitor_tasks 问题)。"""
    from app.api.agent_chat import ConfirmActionRequest, confirm_action
    from app.core.db import get_session_factory

    async def _do():
        body = ConfirmActionRequest(**payload)
        async with get_session_factory()() as s:
            return await confirm_action(
                session_id=sid, message_id=msg_id, body=body, session=s,
            )
    result = asyncio.run(_do())
    return result


def test_reject_with_reason_writes_user_message_with_reason(db_session) -> None:
    """reject 带 reason 时,user 消息 content 应是 reason(不是固定 '取消')。"""
    from app.core.db import get_session_factory
    sid, msg_id = _setup_pending(db_session)

    result = _call_confirm_direct(sid, msg_id, {
        "approved": False, "reason": "想换个角度写,先不要这个版本",
    })
    # result 是 Response 对象,解析
    body = json.loads(result.body)
    assert body["status"] == "cancelled"

    async def _verify():
        async with get_session_factory()() as s:
            fresh = AgentRepository(s)
            msgs = await fresh.list_messages(sid)
            user_msgs = [m for m in msgs if m.role == "user"]
            assert user_msgs, "应有 user 消息"
            latest = user_msgs[-1]
            assert "换个角度" in latest.content or "不要这个版本" in latest.content, (
                f"user 消息应包含 reason,实际: {latest.content!r}"
            )
    asyncio.run(_verify())


def test_reject_without_reason_keeps_default_cancel(db_session) -> None:
    """reject 不传 reason 时,user 消息 content 仍是 '取消'(向后兼容)。"""
    from app.core.db import get_session_factory
    sid, msg_id = _setup_pending(db_session)

    _call_confirm_direct(sid, msg_id, {"approved": False})

    async def _verify():
        async with get_session_factory()() as s:
            fresh = AgentRepository(s)
            msgs = await fresh.list_messages(sid)
            user_msgs = [m for m in msgs if m.role == "user"]
            assert user_msgs
            assert user_msgs[-1].content == "取消"
    asyncio.run(_verify())


def test_reject_with_empty_reason_treated_as_no_reason(db_session) -> None:
    """reason=''(空字符串)应等同未传,写默认 '取消'(不写空字符串)。"""
    from app.core.db import get_session_factory
    sid, msg_id = _setup_pending(db_session)

    _call_confirm_direct(sid, msg_id, {"approved": False, "reason": "   "})

    async def _verify():
        async with get_session_factory()() as s:
            fresh = AgentRepository(s)
            msgs = await fresh.list_messages(sid)
            user_msgs = [m for m in msgs if m.role == "user"]
            # 空字符串被 strip 后视为未传,写 '取消'
            assert user_msgs[-1].content == "取消"
    asyncio.run(_verify())


def test_reject_reason_appears_in_next_turn_messages(db_session) -> None:
    """reject 理由写入历史后,build_messages 能传给 LLM。

    验证:reject reason 是 user role,会被 build_messages 当 user 消息处理。
    """
    from app.domain.agent.turn_helpers import build_messages
    from app.core.db import get_session_factory
    sid, msg_id = _setup_pending(db_session)

    # 模拟 API 写入 reject reason
    async def _do_reject():
        async with get_session_factory()() as s:
            r = AgentRepository(s)
            await r.confirm_message(msg_id, approved=False)
            await r.create_message(
                session_id=sid, role="user",
                content="我想要更正式一点的风格,这个太口语了",
            )
    asyncio.run(_do_reject())

    async def _list():
        async with get_session_factory()() as s:
            r = AgentRepository(s)
            rows = await r.list_messages(sid)
            return [
                {"role": m.role, "content": m.content} for m in rows
            ]
    history = asyncio.run(_list())

    messages = build_messages(history=history)
    user_msgs_in_llm = [m for m in messages if m["role"] == "user"]
    assert any("更正式" in m["content"] for m in user_msgs_in_llm), (
        f"reject reason 应在 build_messages 输出中,实际 user 消息: "
        f"{[m['content'] for m in user_msgs_in_llm]}"
    )
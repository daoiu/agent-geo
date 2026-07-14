"""验证 pending 超时自动取消（P1#25 / Task 26）。

行为契约：
- auto_cancel_pending_messages(timeout_minutes=5) 扫描所有 pending_confirmation=1 的消息
- 找到 created_at 早于 now - timeout_minutes 的,标记 resolved + 追加 "user_timeout" 消息
- 返回取消数量(int)
- 阈值可配(Settings.pending_timeout_minutes)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.agent_repo import AgentRepository


def _make_old_pending(repo, session_id: str, minutes_ago: int = 10):
    """创建一个 pending 消息,created_at 设为 N 分钟前。"""
    async def _do():
        msg = await repo.create_message(
            session_id=session_id, role="assistant", content="...",
            pending_confirmation=True,
        )
        # 修改 created_at 模拟超时(直接操作 ORM 对象)
        from sqlalchemy import update
        from app.models.orm_v04 import AgentMessageORM
        from app.core.db import get_session_factory
        # 用独立 session 改 created_at
        async with get_session_factory()() as s:
            old_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            await s.execute(
                update(AgentMessageORM)
                .where(AgentMessageORM.id == msg.id)
                .values(created_at=old_time)
            )
            await s.commit()
        return msg
    return asyncio.run(_do())


def test_default_pending_timeout_is_5_minutes(monkeypatch) -> None:
    """Settings.pending_timeout_minutes 默认 5。"""
    from app.core.config import get_settings
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    get_settings.cache_clear()  # type: ignore[attr-defined]

    settings = get_settings()
    assert settings.pending_timeout_minutes == 5


def test_auto_cancel_resolves_old_pending(db_session) -> None:
    """auto_cancel_pending_messages 应取消超时(>= 5分钟)的 pending 消息。"""
    from app.domain.agent.pending_timeout import auto_cancel_pending_messages

    repo = AgentRepository(db_session)
    session = await_setup_session(repo)

    # 创建一个 10 分钟前的 pending(应被取消)
    old_msg = _make_old_pending(repo, session.id, minutes_ago=10)

    # 创建一个 1 分钟前的 pending(不应被取消)
    recent_msg = _make_old_pending(repo, session.id, minutes_ago=1)

    # 运行自动取消(默认 5 分钟阈值)
    cancelled = auto_cancel_pending_messages(timeout_minutes=5)
    assert cancelled == 1, f"应取消 1 条超时消息,实际 {cancelled}"

    # 验证 DB(用新 session 避免缓存)
    async def _verify():
        from app.core.db import get_session_factory
        async with get_session_factory()() as s:
            fresh_repo = AgentRepository(s)
            old_after = await fresh_repo.get_message(old_msg.id)
            recent_after = await fresh_repo.get_message(recent_msg.id)
            assert old_after.pending_confirmation == 0, f"超时消息应被 resolved,实际 {old_after.pending_confirmation}"
            assert recent_after.pending_confirmation == 1, "未超时消息应保持 pending"

            # 验证追加了 user_timeout 消息
            msgs = await fresh_repo.list_messages(session.id)
            contents = [m.content for m in msgs]
            assert any("超时" in c or "timeout" in c.lower() for c in contents), (
                f"应追加 user_timeout 消息,实际 {contents}"
            )
    asyncio.run(_verify())


def test_auto_cancel_respects_timeout_minutes(db_session) -> None:
    """timeout_minutes 参数覆盖默认 5。"""
    from app.domain.agent.pending_timeout import auto_cancel_pending_messages

    repo = AgentRepository(db_session)
    session = await_setup_session(repo)

    # 3 分钟前的 pending
    msg = _make_old_pending(repo, session.id, minutes_ago=3)

    # 用 2 分钟阈值 → 应取消(3 > 2)
    cancelled = auto_cancel_pending_messages(timeout_minutes=2)
    assert cancelled == 1

    # 用 5 分钟阈值 → 不应取消(已 resolved)
    msg2 = _make_old_pending(repo, session.id, minutes_ago=3)
    cancelled2 = auto_cancel_pending_messages(timeout_minutes=5)
    assert cancelled2 == 0  # 3 分钟 < 5 分钟,且上一条已 resolved


def test_auto_cancel_zero_when_no_pending(db_session) -> None:
    """无 pending 消息时返回 0,不抛。"""
    from app.domain.agent.pending_timeout import auto_cancel_pending_messages

    # DB 干净
    cancelled = auto_cancel_pending_messages(timeout_minutes=5)
    assert cancelled == 0


def await_setup_session(repo) -> "AgentSessionORM":  # type: ignore
    """同步创建 session 辅助函数。"""
    return asyncio.run(repo.create_session(title="T"))
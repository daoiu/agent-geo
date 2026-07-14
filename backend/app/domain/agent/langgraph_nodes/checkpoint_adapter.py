"""v0.8 CheckpointAdapter(spec §6.2): LangGraph checkpoint ↔ agent_sessions.pending_confirmation 双向投影。

不修改表结构: agent_sessions.pending_confirmation 继续是 source of truth。
新增可空列 langgraph_thread_id,首次发起 CheckpointAdapter 写 uuid4 落表,
用于稳定 LangGraph MemorySaver 的 thread_id。

⚠️ Task 5 骨架: 使用原始 SQL。Task 6 完成后切换到 ORM 实现
    (AgentRepository.get_session_for_resume / update_pending)。
⚠️ langgraph_thread_id 列在 Task 6 添加,Task 5 仅在内存生成 UUID4 不写 DB。
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


class CheckpointAdapter:
    """双向投影: LangGraph __interrupt__ 状态 ↔ agent_sessions.pending_confirmation JSON。

    SessionFactory 可以是 test fixture 创建的内存 SQLite,也可以是真实 DB。
    persist/load_or_init 使用原始 SQL 以便 Task 5 骨架阶段不依赖 ORM 列存在。
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._sf = session_factory
        self._thread_id_cache: dict[str, str] = {}  # session_id -> langgraph_thread_id

    async def load_or_init(self, session_id: str) -> tuple[dict[str, Any], str]:
        """返回 (snapshot, langgraph_thread_id)。

        首次调用时在内存生成 UUID4 作为 thread_id(暂不写 DB,Task 6 迁移后写入)。
        """
        async with self._sf() as session:
            row = await session.execute(
                text(
                    "SELECT pending_confirmation, langgraph_thread_id "
                    "FROM agent_sessions WHERE id = :sid"
                ),
                {"sid": session_id},
            )
            r = row.first()
            if not r:
                return {"messages": [], "pending": None}, ""

            pending_json, thread_id = r[0], r[1]

            # Return cached thread_id if already generated for this session.
            # Task 6 migration: replace this in-memory cache with DB column read/write.
            if session_id in self._thread_id_cache:
                thread_id = self._thread_id_cache[session_id]
            elif thread_id:
                self._thread_id_cache[session_id] = thread_id
            else:
                thread_id = str(uuid.uuid4())
                self._thread_id_cache[session_id] = thread_id

            snapshot = {
                "messages": [],
                "pending": json.loads(pending_json) if pending_json else None,
            }
            return snapshot, thread_id

    async def persist(self, session_id: str, snapshot: dict[str, Any]) -> None:
        """将 snapshot['pending'] 序列化为 JSON 写入 agent_sessions.pending_confirmation。"""
        async with self._sf() as session:
            pending = snapshot.get("pending")
            pending_json = json.dumps(pending) if pending is not None else None
            await session.execute(
                text(
                    "INSERT OR REPLACE INTO agent_sessions (id, pending_confirmation) VALUES (:sid, :p)"
                ),
                {"p": pending_json, "sid": session_id},
            )
            await session.commit()

    async def round_trip(self, session_id: str) -> bool:
        """测试用: 重新加载并验证 pending_confirmation 非空。"""
        snap, _ = await self.load_or_init(session_id)
        return snap.get("pending") is not None

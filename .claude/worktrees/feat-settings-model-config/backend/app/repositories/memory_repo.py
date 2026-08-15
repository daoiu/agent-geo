"""MemoryRepository — AgentMemoryORM 的 CRUD 封装。

L2 跨会话偏好层唯一的数据访问入口。调用方(MemoryService)只走这里,
不直接 ORM。
"""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm_v04 import AgentMemoryORM


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dict(m: AgentMemoryORM | None) -> dict | None:
        if m is None:
            return None
        return {
            "id": m.id,
            "scope": m.scope,
            "name": m.name,
            "description": m.description,
            "type": m.type,
            "body_md": m.body_md,
            "session_id": m.session_id,
            "created_at": m.created_at,
            "updated_at": m.updated_at,
        }

    async def create(
        self,
        *,
        scope: str,
        name: str,
        description: str,
        type: str,
        body_md: str = "",
        session_id: str | None = None,
    ) -> dict:
        m = AgentMemoryORM(
            scope=scope,
            name=name,
            description=description,
            type=type,
            body_md=body_md,
            session_id=session_id,
        )
        self.session.add(m)
        await self.session.commit()
        await self.session.refresh(m)
        return self._to_dict(m)

    async def get_by_id(self, memory_id: str) -> dict | None:
        m = await self.session.get(AgentMemoryORM, memory_id)
        return self._to_dict(m)

    async def get_by_name(self, scope: str, name: str) -> dict | None:
        stmt = select(AgentMemoryORM).where(
            AgentMemoryORM.scope == scope,
            AgentMemoryORM.name == name,
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._to_dict(m)

    async def list_by_scope(self, scope: str) -> list[dict]:
        stmt = (
            select(AgentMemoryORM)
            .where(AgentMemoryORM.scope == scope)
            .order_by(AgentMemoryORM.updated_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_dict(m) for m in rows if m is not None]

    async def count_by_scope(self, scope: str) -> int:
        stmt = (
            select(func.count())
            .select_from(AgentMemoryORM)
            .where(AgentMemoryORM.scope == scope)
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def replace_all_bulk(self, scope: str, items: list[dict]) -> None:
        """consolidate 用:删该 scope 全部,按 items 重建。"""
        await self.session.execute(
            delete(AgentMemoryORM).where(AgentMemoryORM.scope == scope)
        )
        for item in items:
            self.session.add(
                AgentMemoryORM(
                    scope=scope,
                    name=item["name"],
                    description=item["description"],
                    type=item["type"],
                    body_md=item.get("body_md", ""),
                    session_id=item.get("session_id"),
                )
            )
        await self.session.commit()

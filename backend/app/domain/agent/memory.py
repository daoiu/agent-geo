"""MemoryService — 跨会话偏好层(L2)。

照搬 s09 架构 (`D:/Agent/learn-claude-code/s09_memory/code.py`),
把 fs 后端换为 SQLite + MemoryRepository。函数名一一对应:

    s09                                  →  本文件
    write_memory_file(name, type, ...)  →  write_memory(scope, name, type, ...)
    read_memory_index()                 →  read_memory_index(scope)
    read_memory_file(filename)          →  read_memory(memory_id)
    list_memory_files()                 →  list_memories(scope)
    select_relevant_memories(msgs)      →  select_relevant(scope, msgs, k)
    load_memories(msgs)                 →  load_relevant_memories(scope, msgs)
    extract_memories(msgs)              →  extract(scope, msgs, session_id)
    consolidate_memories()              →  consolidate(scope)
    build_system() 的索引段              →  build_memory_segment(scope)

新增:scope_key(device_id, session_id) 助手函数。
"""
from __future__ import annotations

import json
import re
import time

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.agent.memory_vector import MemoryVectorIndex
from app.domain.llm_client import LLMClient
from app.repositories.memory_repo import MemoryRepository
from app.services.embedding import EmbeddingService

logger = structlog.get_logger()

MEMORY_TYPES = {"user", "feedback", "project", "reference"}

_SYSTEM_PROMPT_SEGMENT_HEADER = "Memories available (cross-session preferences)"


def scope_key(device_id: str | None, session_id: str) -> str:
    """L2 跨会话偏好池的隔离 key。

    优先用 device_id(跨 session 共享)。缺失/非法时降级为
    `anon:<session_id>`,保证匿名场景也有 scope。
    """
    return device_id if device_id else f"anon:{session_id}"


class MemoryService:
    def __init__(
        self,
        session: AsyncSession,
        threshold: int | None = None,
    ):
        self.session = session
        self.repo = MemoryRepository(session)
        self.threshold = (
            threshold
            if threshold is not None
            else get_settings().memory_consolidate_threshold
        )

    # ------------------------------------------------------------------
    # list / index
    # ------------------------------------------------------------------

    async def list_memories(self, scope: str) -> list[dict]:
        return await self.repo.list_by_scope(scope)

    async def read_memory_index(self, scope: str) -> str:
        rows = await self.list_memories(scope)
        if not rows:
            return ""
        return "\n".join(
            f"- {r['name']} — {r['description']}" for r in rows
        )

    async def build_memory_segment(self, scope: str) -> str:
        """拼到 AGENT_SYSTEM_PROMPT 末尾的索引段(无 LLM 调用)。"""
        idx = await self.read_memory_index(scope)
        if not idx:
            return ""
        return f"\n\n{_SYSTEM_PROMPT_SEGMENT_HEADER}\n{idx}\n"

    async def read_memory(self, memory_id: str) -> dict | None:
        return await self.repo.get_by_id(memory_id)

    # ------------------------------------------------------------------
    # write
    # ------------------------------------------------------------------

    async def write_memory(
        self,
        *,
        scope: str,
        name: str,
        type: str,
        description: str,
        body: str,
        session_id: str | None = None,
    ) -> dict:
        if type not in MEMORY_TYPES:
            raise ValueError(f"unknown memory type: {type}")
        created = await self.repo.create(
            scope=scope,
            name=name,
            description=description,
            type=type,
            body_md=body,
            session_id=session_id,
        )
        try:
            emb = EmbeddingService.embed([self._embed_text(name, description)])[0]
            MemoryVectorIndex().add(
                created["id"], scope, type,
                self._embed_text(name, description), emb,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("write_memory_vector_failed",
                           scope=scope, name=name, error=str(e))
        return created

    @staticmethod
    def _embed_text(name: str, description: str) -> str:
        return f"{name}。{description}"

    async def _ensure_vectors(self, scope: str) -> None:
        """lazy 回填:补齐该 scope 在向量库缺失的记忆。失败静默。"""
        try:
            rows = await self.repo.list_by_scope(scope)
            if not rows:
                return
            vidx = MemoryVectorIndex()
            have = vidx.ids_in_scope(scope)
            missing = [r for r in rows if r["id"] not in have]
            if not missing:
                return
            texts = [self._embed_text(r["name"], r["description"]) for r in missing]
            embs = EmbeddingService.embed(texts)
            for r, e in zip(missing, embs):
                vidx.add(r["id"], scope, r["type"],
                         self._embed_text(r["name"], r["description"]), e)
        except Exception as e:  # noqa: BLE001
            logger.warning("ensure_vectors_failed", scope=scope, error=str(e))

    # ------------------------------------------------------------------
    # select_relevant — LLM 选相关,失败降级关键词
    # ------------------------------------------------------------------

    @staticmethod
    def _recent_user_text(messages: list[dict]) -> str:
        """取最近 ≤3 条 user 消息拼成查询上下文。"""
        recent_texts: list[str] = []
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        str(b.get("text", ""))
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                if isinstance(content, str) and content.strip():
                    recent_texts.append(content)
                if len(recent_texts) >= 3:
                    break
        return " ".join(reversed(recent_texts))[:2000]

    async def select_relevant(
        self,
        scope: str,
        messages: list[dict],
        k: int = 5,
    ) -> list[dict]:
        recent = self._recent_user_text(messages)
        if not recent.strip():
            return []

        await self._ensure_vectors(scope)
        try:
            qv = EmbeddingService.embed([recent])[0]
            hits = MemoryVectorIndex().query(qv, scope, top_k=k)
            out: list[dict] = []
            for h in hits:
                row = await self.repo.get_by_id(h["id"])
                if row:
                    out.append(row)
            return out
        except Exception as e:  # noqa: BLE001
            logger.warning("select_relevant_vector_failed",
                           scope=scope, error=str(e))
            rows = await self.repo.list_by_scope(scope)
            return rows[:k]

    async def load_relevant_memories(
        self,
        scope: str,
        messages: list[dict],
        k: int = 5,
    ) -> str:
        """拼出 `<relevant_memories>...</>` XML 块,空集合 → 空字符串。"""
        selected = await self.select_relevant(scope, messages, k=k)
        if not selected:
            return ""
        parts = ["<relevant_memories>"]
        for r in selected:
            parts.append(
                f"---\n"
                f"name: {r['name']}\n"
                f"description: {r['description']}\n"
                f"type: {r['type']}\n\n"
                f"{r['body_md']}\n"
            )
        parts.append("</relevant_memories>")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # extract — LLM 从对话蒸馏新记忆,同名跳过
    # ------------------------------------------------------------------

    async def extract(
        self,
        scope: str,
        messages: list[dict],
        session_id: str | None = None,
    ) -> int:
        # Phase 2 门控:最近 user 文本过短则跳过(不调 LLM)
        recent = self._recent_user_text(messages)
        if len(recent.strip()) < get_settings().memory_extract_min_chars:
            return 0

        dialogue_parts: list[str] = []
        for msg in messages[-10:]:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(b.get("text", ""))
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            if isinstance(content, str) and content.strip():
                dialogue_parts.append(f"{role}: {content}")
        dialogue = "\n".join(dialogue_parts)
        if not dialogue.strip():
            return 0

        existing = await self.list_memories(scope)
        existing_desc = (
            "\n".join(f"- {r['name']}: {r['description']}" for r in existing)
            if existing else "(none)"
        )

        prompt = (
            "Extract user preferences, constraints, or project facts from this "
            "dialogue.\n"
            "Return a JSON array. Each item: {name, type, description, body}.\n"
            "- name: short kebab-case slug\n"
            f"- type: one of {sorted(MEMORY_TYPES)}\n"
            "- description: one-line summary\n"
            "- body: full detail in markdown\n"
            "If nothing new or already covered, return [].\n\n"
            f"Existing memories:\n{existing_desc}\n\n"
            f"Dialogue:\n{dialogue[:4000]}"
        )

        try:
            settings = get_settings()
            llm = LLMClient(settings)
            response = await llm.simple_chat(prompt=prompt)
            match = re.search(r"\[.*\]", response, re.DOTALL)
            if not match:
                return 0
            items = json.loads(match.group())
        except Exception as e:  # noqa: BLE001
            logger.warning("extract_failed", error=str(e))
            return 0

        count = 0
        for idx, item in enumerate(items):
            name = item.get("name") or f"memory_{int(time.time())}_{idx}"
            mtype = item.get("type", "user")
            desc = item.get("description", "")
            body = item.get("body", "")
            if mtype not in MEMORY_TYPES or not desc or not body:
                continue
            existing_match = await self.repo.get_by_name(scope, name)
            if existing_match:
                continue
            # Phase 2 向量近邻语义去重(失败降级 exact-name only)
            try:
                cv = EmbeddingService.embed([self._embed_text(name, desc)])[0]
                nearest = MemoryVectorIndex().query(cv, scope, top_k=1)
                if nearest and nearest[0]["distance"] is not None and \
                        nearest[0]["distance"] < get_settings().memory_dedup_max_distance:
                    continue
            except Exception as e:  # noqa: BLE001
                logger.warning("extract_dedup_vector_failed",
                               scope=scope, name=name, error=str(e))
            await self.write_memory(
                scope=scope,
                name=name,
                type=mtype,
                description=desc,
                body=body,
                session_id=session_id,
            )
            count += 1

        # 阈值触发整理(行数 ≥ 阈值)
        try:
            if await self.repo.count_by_scope(scope) >= self.threshold:
                await self.consolidate(scope)
        except Exception as e:  # noqa: BLE001
            logger.warning("auto_consolidate_failed", error=str(e))

        return count

    # ------------------------------------------------------------------
    # consolidate — 阈值触发,LLM 合并去重淘汰
    # ------------------------------------------------------------------

    async def consolidate(self, scope: str) -> int:
        rows = await self.list_memories(scope)
        if len(rows) < self.threshold:
            return len(rows)

        catalog = "\n\n".join(
            f"## {r['name']}\n"
            f"name: {r['name']}\n"
            f"description: {r['description']}\n"
            f"type: {r['type']}\n"
            f"{r['body_md']}"
            for r in rows
        )
        prompt = (
            "Consolidate the following memory files. Rules:\n"
            "1. Merge duplicates into one\n"
            "2. Remove outdated/contradicted memories\n"
            "3. Keep the total under 30 memories\n"
            "4. Preserve important user preferences above all\n"
            "Return a JSON array. Each item: "
            "{name, type, description, body}.\n\n"
            f"{catalog[:16000]}"
        )

        try:
            settings = get_settings()
            llm = LLMClient(settings)
            response = await llm.simple_chat(prompt=prompt)
            match = re.search(r"\[.*\]", response, re.DOTALL)
            if not match:
                return len(rows)
            items = json.loads(match.group())
        except Exception as e:  # noqa: BLE001
            logger.warning("consolidate_failed", error=str(e))
            return len(rows)

        new_items: list[dict] = []
        for item in items:
            name = item.get("name") or f"consolidated_{int(time.time())}_{len(new_items)}"
            mtype = item.get("type", "user")
            desc = item.get("description", "")
            body = item.get("body", "")
            if mtype in MEMORY_TYPES and desc and body:
                new_items.append({
                    "name": name,
                    "type": mtype,
                    "description": desc,
                    "body_md": body,
                })
        await self.repo.replace_all_bulk(scope, new_items)
        # Phase 2:同步向量(清 scope 旧向量,为新记录回填;失败静默,下次 select 补)
        try:
            vidx = MemoryVectorIndex()
            vidx.delete_scope(scope)
            fresh = await self.repo.list_by_scope(scope)
            if fresh:
                texts = [self._embed_text(r["name"], r["description"]) for r in fresh]
                embs = EmbeddingService.embed(texts)
                for r, e in zip(fresh, embs):
                    vidx.add(r["id"], scope, r["type"],
                             self._embed_text(r["name"], r["description"]), e)
        except Exception as e:  # noqa: BLE001
            logger.warning("consolidate_vector_sync_failed",
                           scope=scope, error=str(e))
        logger.info(
            "memory_consolidated", scope=scope, old=len(rows), new=len(new_items)
        )
        return len(new_items)

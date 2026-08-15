"""ChromaDB 单 collection 封装 L2 记忆向量(Phase 2)。

collection "agent_memories":scope 存 metadata,一条记忆一个向量。
真相源是 SQLite AgentMemoryORM;本索引可重建。
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

_COLLECTION = "agent_memories"


class MemoryVectorIndex:
    _client = None  # process-singleton

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            settings = get_settings()
            cls._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return cls._client

    def __init__(self) -> None:
        client = self._get_client()
        self._c = client.get_or_create_collection(
            name=_COLLECTION, metadata={"hnsw:space": "cosine"},
        )

    def add(self, memory_id: str, scope: str, mtype: str,
            text: str, embedding: list[float]) -> None:
        self._c.upsert(
            ids=[memory_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[{"scope": scope, "type": mtype}],
        )

    def query(self, embedding: list[float], scope: str,
              top_k: int = 5) -> list[dict]:
        res = self._c.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"scope": scope},
        )
        ids = res.get("ids", [[]])[0] if res.get("ids") else []
        dists = res.get("distances", [[]])[0] if res.get("distances") else []
        return [
            {"id": ids[i], "distance": dists[i] if i < len(dists) else None}
            for i in range(len(ids))
        ]

    def delete_scope(self, scope: str) -> None:
        self._c.delete(where={"scope": scope})

    def ids_in_scope(self, scope: str) -> set[str]:
        res = self._c.get(where={"scope": scope})
        return set(res.get("ids", []))

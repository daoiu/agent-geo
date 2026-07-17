"""ChromaDB wrapper for knowledge base chunk vectors.

One ChromaDB collection per knowledge base (named "kb_{kb_id}").
The ChromaDB PersistentClient is process-singleton (class-level cached).
"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings


class VectorIndex:
    """Thin wrapper around a ChromaDB collection for one knowledge base."""

    _client = None  # process-singleton (ChromaDB client is thread-safe)

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            settings = get_settings()
            cls._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return cls._client

    def __init__(self, kb_id: str) -> None:
        self.kb_id = kb_id
        client = self._get_client()
        self._collection = client.get_or_create_collection(
            name=f"kb_{kb_id}",
            metadata={"hnsw:space": "cosine"},  # use cosine distance
        )

    def add_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """Add chunks to the index.

        chunks: [{'id', 'content', 'doc_id', 'chunk_index'}, ...]
        embeddings: 预计算的 bge 向量(每 chunk 一个 512 维向量,顺序与 chunks 对齐)。
                     **必须**传入,否则 ChromaDB 会用其默认 embedding function(英文、
                     384 维)与 bge-small-zh-v1.5(中文、512 维)不一致,导致语义检索错误。
        """
        if not chunks:
            return
        if embeddings is None:
            raise ValueError(
                "embeddings 必须由调用方预计算(EmbeddingService.embed),"
                "否则 ChromaDB 会用默认 embedding function 与 bge 不一致"
            )
        if len(embeddings) != len(chunks):
            raise ValueError(
                f"embeddings 长度({len(embeddings)})与 chunks 长度({len(chunks)})不匹配"
            )
        self._collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["content"] for c in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "doc_id": c["doc_id"],
                    "chunk_index": c["chunk_index"],
                    "kb_id": self.kb_id,
                }
                for c in chunks
            ],
        )

    def query(
        self,
        query_text: str | None = None,
        *,
        query_embedding: list[float] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Query by semantic similarity. Returns list of {id, content, metadata, distance}.

        推荐路径:传 query_embedding(由调用方用 EmbeddingService.embed 预计算,512 维),
        避免 ChromaDB 用默认 384 维英文 embedding function 与 bge-small-zh-v1.5 不一致。

        query_text 路径保留向后兼容,但会触发 ChromaDB 内部 embedding 转换,
        与当前 collection 的 bge 512 维向量不在同一空间,可能导致维度不匹配错误。
        """
        if query_embedding is None and query_text is None:
            raise ValueError("query_text 和 query_embedding 必须至少传一个")
        if query_embedding is not None and query_text is not None:
            raise ValueError("query_text 和 query_embedding 互斥,只传一个")

        if query_embedding is not None:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )
        else:
            # 向后兼容:走 ChromaDB 内部 embedding 转换(可能 384 维与 collection 512 维冲突)
            results = self._collection.query(
                query_texts=[query_text],
                n_results=top_k,
            )
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        docs = results.get("documents", [[]])[0] if results.get("documents") else []
        metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        dists = results.get("distances", [[]])[0] if results.get("distances") else []
        return [
            {
                "id": ids[i],
                "content": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None,
            }
            for i in range(len(ids))
        ]

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Delete chunks by ID."""
        if chunk_ids:
            self._collection.delete(ids=chunk_ids)

    def get_all_ids(self) -> set[str]:
        """Return all chunk IDs in the index (used by reindex for diff)."""
        result = self._collection.get()
        return set(result.get("ids", []))
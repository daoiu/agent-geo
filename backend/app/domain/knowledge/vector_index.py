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

    def add_chunks(self, chunks: list[dict]) -> None:
        """Add chunks to the index.

        chunks: [{'id', 'content', 'doc_id', 'chunk_index'}, ...]
        """
        if not chunks:
            return
        self._collection.add(
            ids=[c["id"] for c in chunks],
            documents=[c["content"] for c in chunks],
            metadatas=[
                {
                    "doc_id": c["doc_id"],
                    "chunk_index": c["chunk_index"],
                    "kb_id": self.kb_id,
                }
                for c in chunks
            ],
        )

    def query(self, query_text: str, top_k: int = 10) -> list[dict]:
        """Query by semantic similarity. Returns list of {id, content, metadata, distance}."""
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
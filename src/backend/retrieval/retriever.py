from __future__ import annotations

from src.backend.models import ChunkMetadata
from src.backend.retrieval.vector_store import VectorStore


def retrieve_chunks(
    chunks: list[ChunkMetadata],
    requirement_ids: list[str] | None = None,
    user_query: str | None = None,
    top_k: int = 5,
    vector_store: VectorStore | None = None,
) -> list[ChunkMetadata]:
    if requirement_ids:
        wanted = set(requirement_ids)
        selected = [chunk for chunk in chunks if chunk.requirement_id in wanted]
        if selected:
            return selected[:top_k]

    if vector_store is not None:
        query_text = (user_query or "").strip() or " ".join(requirement_ids or []) or "requirements"
        vector_rows = vector_store.query(query_text=query_text, top_k=top_k)
        if vector_rows:
            return vector_rows

    return chunks[:top_k]

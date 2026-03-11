from __future__ import annotations

from typing import Protocol

from src.backend.models import ChunkMetadata


class VectorStore(Protocol):
    def upsert_chunks(self, chunks: list[ChunkMetadata]) -> None: ...

    def query(self, query_text: str, top_k: int) -> list[ChunkMetadata]: ...

    def clear(self) -> None: ...

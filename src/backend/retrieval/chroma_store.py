from __future__ import annotations

import hashlib
from typing import Sequence, cast

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.api.types import Metadata

from src.backend.models import ChunkMetadata
from src.core.config import settings

def _embed(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    tokens = text.lower().split()
    if not tokens:
        return vector
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for idx in range(dims):
            vector[idx] += digest[idx % len(digest)] / 255.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


class ChromaVectorStore:
    def __init__(self) -> None:
        self._collection: Collection | None = None

    def _get_collection(self) -> Collection:
        if self._collection is not None:
            return self._collection

        chroma_path = settings.chroma_path.resolve()
        chroma_path.mkdir(parents=True, exist_ok=True)
        try:
            client = chromadb.PersistentClient(path=str(chroma_path))
            self._collection = client.get_or_create_collection(name="qa_chunks")
        except Exception:
            client = chromadb.EphemeralClient()
            self._collection = client.get_or_create_collection(name="qa_chunks")
        return self._collection

    def upsert_chunks(self, chunks: list[ChunkMetadata]) -> None:
        if not chunks:
            return
        collection = self._get_collection()
        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        embeddings: list[Sequence[float]] = [_embed(chunk.content) for chunk in chunks]
        metadatas: list[Metadata] = [
            {
                "requirement_id": chunk.requirement_id,
                "source_doc": chunk.source_doc,
                "source_location": chunk.source_location,
                "section_title": chunk.section_title,
                "chunk_type": chunk.chunk_type,
            }
            for chunk in chunks
        ]
        collection.upsert(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)

    def query(self, query_text: str, top_k: int) -> list[ChunkMetadata]:
        collection = self._get_collection()
        query_embeddings: list[Sequence[float]] = [_embed(query_text)]
        result = collection.query(query_embeddings=query_embeddings, n_results=top_k)
        ids_nested = cast(list[list[str]], result.get("ids") or [[]])
        docs_nested = cast(list[list[str]], result.get("documents") or [[]])
        metas_nested = cast(list[list[Metadata]], result.get("metadatas") or [[]])

        ids = ids_nested[0] if ids_nested else []
        documents = docs_nested[0] if docs_nested else []
        metadatas = metas_nested[0] if metas_nested else []

        rows: list[ChunkMetadata] = []
        for chunk_id, content, metadata in zip(ids, documents, metadatas):
            rows.append(
                ChunkMetadata(
                    chunk_id=str(chunk_id),
                    requirement_id=str(metadata.get("requirement_id", "확인 필요")),
                    source_doc=str(metadata.get("source_doc", "")),
                    source_location=str(metadata.get("source_location", "")),
                    section_title=str(metadata.get("section_title", "")),
                    chunk_type=str(metadata.get("chunk_type", "requirement")),
                    content=str(content),
                )
            )
        return rows

    def clear(self) -> None:
        collection = self._get_collection()
        ids = cast(list[str], collection.get(include=[]).get("ids", []))
        if ids:
            collection.delete(ids=ids)


chroma_store = ChromaVectorStore()

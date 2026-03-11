from __future__ import annotations

import re
from uuid import uuid4

from src.backend.models import ChunkMetadata, NormalizedDocument

REQ_ID_PATTERN = re.compile(r"\b[A-Z]{2,}-\d+\b")


def build_chunks(normalized_document: NormalizedDocument) -> list[ChunkMetadata]:
    chunks: list[ChunkMetadata] = []
    for section in normalized_document.sections:
        req_ids = sorted(set(REQ_ID_PATTERN.findall(section.content)))
        ids = req_ids if req_ids else ["확인 필요"]
        for requirement_id in ids:
            chunks.append(
                ChunkMetadata(
                    chunk_id=str(uuid4()),
                    requirement_id=requirement_id,
                    source_doc=normalized_document.filename,
                    source_location=section.source_location,
                    section_title=section.section_title,
                    chunk_type="requirement",
                    content=section.content,
                )
            )
    return chunks

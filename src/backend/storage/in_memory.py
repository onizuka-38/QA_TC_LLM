from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from src.backend.models import (
    AuditRecord,
    ChunkMetadata,
    JobRecord,
    NormalizedDocument,
    ParserOutput,
    RTMRow,
    ValidationRecord,
)


@dataclass
class InMemoryStore:
    documents: dict[str, ParserOutput] = field(default_factory=dict)
    normalized_docs: dict[str, NormalizedDocument] = field(default_factory=dict)
    chunks: dict[str, list[ChunkMetadata]] = field(default_factory=dict)
    jobs: dict[str, JobRecord] = field(default_factory=dict)
    validations: dict[str, ValidationRecord] = field(default_factory=dict)
    rtm_rows: dict[str, list[RTMRow]] = field(default_factory=dict)
    exports: dict[str, bytes] = field(default_factory=dict)
    audits: list[AuditRecord] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def set_job(self, request_id: str, payload: JobRecord) -> None:
        with self._lock:
            self.jobs[request_id] = payload


store = InMemoryStore()

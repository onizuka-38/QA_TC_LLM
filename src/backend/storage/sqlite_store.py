from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from src.backend.models import (
    AuditRecord,
    ChunkMetadata,
    GenerationRecord,
    JobRecord,
    RTMRow,
    ReviewHistoryRecord,
    ValidationRecord,
)
from src.core.config import settings


class SQLiteStore:
    def __init__(self) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_pragmas()
        self._init_schema()

    def _init_pragmas(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def _init_schema(self) -> None:
        ddl = [
            """
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                source_location TEXT NOT NULL,
                content_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS normalized_documents (
                document_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS jobs (
                request_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS validations (
                request_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rtm_rows (
                request_id TEXT NOT NULL,
                row_index INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (request_id, row_index)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS exports (
                request_id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_format TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS generation_records (
                request_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """,
        ]
        for query in ddl:
            self._conn.execute(query)
        self._conn.commit()

    def save_document(self, *, document_id: str, filename: str, file_type: str, extracted_text: str, source_location: str, content_path: str) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO documents(document_id, filename, file_type, extracted_text, source_location, content_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (document_id, filename, file_type, extracted_text, source_location, content_path, datetime.utcnow().isoformat()),
        )
        self._conn.commit()

    def save_normalized_document(self, document_id: str, payload: dict[str, object]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO normalized_documents(document_id, payload_json) VALUES (?, ?)",
            (document_id, json.dumps(payload, ensure_ascii=False)),
        )
        self._conn.commit()

    def save_chunks(self, document_id: str, chunks: list[ChunkMetadata]) -> None:
        self._conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        for chunk in chunks:
            self._conn.execute(
                "INSERT INTO chunks(chunk_id, document_id, payload_json) VALUES (?, ?, ?)",
                (chunk.chunk_id, document_id, json.dumps(chunk.model_dump(mode='json'), ensure_ascii=False)),
            )
        self._conn.commit()

    def get_chunks_by_document(self, document_id: str) -> list[ChunkMetadata]:
        rows = self._conn.execute("SELECT payload_json FROM chunks WHERE document_id = ?", (document_id,)).fetchall()
        return [ChunkMetadata.model_validate(json.loads(row["payload_json"])) for row in rows]

    def set_job(self, payload: JobRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO jobs(request_id, payload_json) VALUES (?, ?)",
            (payload.request_id, json.dumps(payload.model_dump(mode='json'), ensure_ascii=False)),
        )
        self._conn.commit()

    def get_job(self, request_id: str) -> JobRecord | None:
        row = self._conn.execute("SELECT payload_json FROM jobs WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        return JobRecord.model_validate(json.loads(row["payload_json"]))

    def save_validation(self, payload: ValidationRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO validations(request_id, payload_json) VALUES (?, ?)",
            (payload.request_id, json.dumps(payload.model_dump(mode='json'), ensure_ascii=False)),
        )
        self._conn.commit()

    def get_validation(self, request_id: str) -> ValidationRecord | None:
        row = self._conn.execute("SELECT payload_json FROM validations WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        return ValidationRecord.model_validate(json.loads(row["payload_json"]))

    def save_rtm_rows(self, request_id: str, rows: list[RTMRow]) -> None:
        self._conn.execute("DELETE FROM rtm_rows WHERE request_id = ?", (request_id,))
        for index, row in enumerate(rows):
            self._conn.execute(
                "INSERT INTO rtm_rows(request_id, row_index, payload_json) VALUES (?, ?, ?)",
                (request_id, index, json.dumps(row.model_dump(mode='json'), ensure_ascii=False)),
            )
        self._conn.commit()

    def get_rtm_rows(self, request_id: str) -> list[RTMRow]:
        rows = self._conn.execute(
            "SELECT payload_json FROM rtm_rows WHERE request_id = ? ORDER BY row_index",
            (request_id,),
        ).fetchall()
        return [RTMRow.model_validate(json.loads(row["payload_json"])) for row in rows]

    def save_export_metadata(self, *, request_id: str, file_path: str, file_format: str, size_bytes: int) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO exports(request_id, file_path, file_format, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, file_path, file_format, size_bytes, datetime.utcnow().isoformat()),
        )
        self._conn.commit()

    def get_export_metadata(self, request_id: str) -> dict[str, object] | None:
        row = self._conn.execute(
            "SELECT file_path, file_format, size_bytes, created_at FROM exports WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "file_path": str(row["file_path"]),
            "file_format": str(row["file_format"]),
            "size_bytes": int(row["size_bytes"]),
            "created_at": str(row["created_at"]),
        }

    def append_audit(self, payload: AuditRecord) -> None:
        self._conn.execute(
            "INSERT INTO audits(payload_json) VALUES (?)",
            (json.dumps(payload.model_dump(mode='json'), ensure_ascii=False),),
        )
        self._conn.commit()

    def save_generation_record(self, payload: GenerationRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO generation_records(request_id, payload_json) VALUES (?, ?)",
            (payload.request_id, json.dumps(payload.model_dump(mode='json'), ensure_ascii=False)),
        )
        self._conn.commit()

    def append_review_history(self, payload: ReviewHistoryRecord) -> None:
        self._conn.execute(
            "INSERT INTO review_history(request_id, payload_json) VALUES (?, ?)",
            (payload.request_id, json.dumps(payload.model_dump(mode='json'), ensure_ascii=False)),
        )
        self._conn.commit()

    def clear_all(self) -> None:
        for table in [
            "documents",
            "normalized_documents",
            "chunks",
            "jobs",
            "validations",
            "rtm_rows",
            "exports",
            "audits",
            "generation_records",
            "review_history",
        ]:
            self._conn.execute(f"DELETE FROM {table}")
        self._conn.commit()


sqlite_store = SQLiteStore()

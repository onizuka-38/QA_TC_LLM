from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from src.backend.audit.logger import build_audit_record
from src.backend.generation.tc_generator import TCGenerator
from src.backend.models import (
    ChunkMetadata,
    GenerationRecord,
    JobRecord,
    JobStatus,
    RTMRow,
    ReviewHistoryRecord,
    ReviewStatus,
    ValidationRecord,
)
from src.backend.normalize.normalizer import normalize_document
from src.backend.output.excel_writer import build_excel_xlsx
from src.backend.output.rtm_builder import build_rtm_rows
from src.backend.parsers.factory import ParserFactory
from src.backend.retrieval.chroma_store import chroma_store
from src.backend.retrieval.chunker import build_chunks
from src.backend.retrieval.retriever import retrieve_chunks
from src.backend.storage.file_store import file_store
from src.backend.storage.sqlite_store import sqlite_store
from src.backend.validation.tc_validator import validate_tc_list
from src.core.config import settings

ALLOWED_FILE_TYPES = {"pdf", "docx", "xlsx"}


class WorkflowService:
    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._generator = TCGenerator()

    async def upload_documents(self, files: list[UploadFile], requested_by: str) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for file in files:
            document_id = str(uuid4())
            ext = Path(file.filename or "").suffix.lstrip(".").lower()
            if ext not in ALLOWED_FILE_TYPES:
                raise ValueError(f"unsupported file type: {ext}")

            content = await file.read()
            parser = ParserFactory.resolve(ext)
            parsed = parser.parse(document_id=document_id, filename=file.filename or document_id, content=content)
            normalized = normalize_document(parsed)
            chunks = build_chunks(normalized)

            content_path = file_store.save_upload(document_id=document_id, filename=parsed.filename, content=content)
            sqlite_store.save_document(
                document_id=parsed.document_id,
                filename=parsed.filename,
                file_type=parsed.file_type,
                extracted_text=parsed.extracted_text,
                source_location=parsed.source_location,
                content_path=content_path,
            )
            sqlite_store.save_normalized_document(document_id, normalized.model_dump(mode="json"))
            sqlite_store.save_chunks(document_id, chunks)
            chroma_store.upsert_chunks(chunks)
            results.append({"document_id": document_id, "filename": parsed.filename, "file_type": parsed.file_type})

        sqlite_store.append_audit(build_audit_record("-", "upload", "completed", settings.model_name, requested_by))
        return results

    async def generate(
        self,
        document_ids: list[str],
        requirement_ids: list[str],
        user_prompt: str,
        requested_by: str,
    ) -> str:
        request_id = str(uuid4())
        sqlite_store.set_job(
            JobRecord(
                request_id=request_id,
                status=JobStatus.queued,
                created_at=datetime.now(timezone.utc),
                document_ids=document_ids,
            )
        )

        async with self._sem:
            job = sqlite_store.get_job(request_id)
            if job is None:
                raise RuntimeError("job persistence failed")
            sqlite_store.set_job(job.model_copy(update={"status": JobStatus.processing}))

            merged_chunks: list[ChunkMetadata] = []
            for document_id in document_ids:
                merged_chunks.extend(sqlite_store.get_chunks_by_document(document_id))

            selected = retrieve_chunks(
                merged_chunks,
                requirement_ids=requirement_ids,
                vector_store=chroma_store,
            )

            sqlite_store.save_generation_record(
                GenerationRecord(
                    request_id=request_id,
                    model_version=settings.model_name,
                    prompt_version="v1",
                    generated_at=datetime.now(timezone.utc),
                    source_chunks=[chunk.chunk_id for chunk in selected],
                )
            )

            cases, review_required = await self._generator.generate(selected, user_prompt=user_prompt)
            if review_required:
                self._mark_review_required(request_id, requested_by)
                sqlite_store.save_validation(
                    ValidationRecord(
                        request_id=request_id,
                        validated_at=datetime.now(timezone.utc),
                        result=validate_tc_list([]),
                    )
                )
                return request_id

            validation = validate_tc_list(cases)
            sqlite_store.save_validation(
                ValidationRecord(
                    request_id=request_id,
                    validated_at=datetime.now(timezone.utc),
                    result=validation,
                )
            )

            if validation.is_valid:
                rtm_rows = build_rtm_rows(cases)
                sqlite_store.save_rtm_rows(request_id, rtm_rows)
                export_bytes = build_excel_xlsx(cases, rtm_rows)
                export_path = file_store.save_export_xlsx(request_id=request_id, content=export_bytes)
                sqlite_store.save_export_metadata(
                    request_id=request_id,
                    file_path=export_path,
                    file_format="xlsx",
                    size_bytes=len(export_bytes),
                )
                sqlite_store.set_job(job.model_copy(update={"status": JobStatus.completed, "tc_count": len(cases)}))
                sqlite_store.append_audit(build_audit_record(request_id, "generate", "completed", settings.model_name, requested_by))
            else:
                self._mark_review_required(request_id, requested_by)
        return request_id

    def _mark_review_required(self, request_id: str, requested_by: str) -> None:
        job = sqlite_store.get_job(request_id)
        if job is None:
            return
        sqlite_store.set_job(job.model_copy(update={"status": JobStatus.review_required}))
        sqlite_store.append_audit(build_audit_record(request_id, "generate", "review_required", settings.model_name, requested_by))
        sqlite_store.append_review_history(
            ReviewHistoryRecord(
                request_id=request_id,
                status=ReviewStatus.check_required,
                reviewer=requested_by,
                reviewed_at=datetime.now(timezone.utc),
                note="JSON 구조화 출력 실패 또는 검증 실패",
            )
        )

    def get_job(self, request_id: str) -> JobRecord | None:
        return sqlite_store.get_job(request_id)

    def get_validation(self, request_id: str) -> ValidationRecord | None:
        return sqlite_store.get_validation(request_id)

    def get_rtm(self, request_id: str) -> list[RTMRow]:
        return sqlite_store.get_rtm_rows(request_id)

    def get_export(self, request_id: str) -> bytes | None:
        metadata = sqlite_store.get_export_metadata(request_id)
        if metadata is None:
            return None
        return file_store.load_bytes(str(metadata["file_path"]))


workflow_service = WorkflowService()

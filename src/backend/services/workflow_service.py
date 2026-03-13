from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from src.backend.audit.logger import build_audit_record
from src.backend.generation.tc_generator import TCGenerator
from src.backend.generation.vllm_client import VLLMClient
from src.backend.models import (
    ChatRecord,
    ChunkMetadata,
    EditHistoryRecord,
    GenerationRecord,
    JobRecord,
    JobStatus,
    RequirementOption,
    RTMRow,
    ReviewHistoryRecord,
    ReviewStatus,
    TestCase,
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
        self._vllm_client = VLLMClient()

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
        target_case_count: int | None,
        requested_by: str,
    ) -> str:
        if not requirement_ids:
            raise ValueError("selected requirement_ids are required")

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

            merged_chunks = self._merge_chunks(document_ids)

            selected = retrieve_chunks(
                merged_chunks,
                requirement_ids=requirement_ids,
                vector_store=chroma_store,
            )
            selected_set = set(requirement_ids)
            selected = [chunk for chunk in selected if chunk.requirement_id in selected_set]
            if not selected:
                selected = [chunk for chunk in merged_chunks if chunk.requirement_id in selected_set]
            selected = self._limit_chunks_for_prompt(selected, max_per_requirement=1, max_total=8)
            if not selected:
                self._mark_review_required(request_id, requested_by)
                sqlite_store.save_tc_draft(request_id, [])
                sqlite_store.set_review_state(request_id, is_reviewed=False, last_edited_at=None)
                sqlite_store.save_validation(
                    ValidationRecord(
                        request_id=request_id,
                        validated_at=datetime.now(timezone.utc),
                        result=validate_tc_list([], requirement_ids=requirement_ids, target_case_count=target_case_count),
                    )
                )
                return request_id

            sqlite_store.save_generation_record(
                GenerationRecord(
                    request_id=request_id,
                    model_version=settings.model_name,
                    prompt_version="v1",
                    generated_at=datetime.now(timezone.utc),
                    selected_requirement_ids=requirement_ids,
                    target_case_count=target_case_count,
                    source_chunks=[chunk.chunk_id for chunk in selected],
                )
            )

            generation_prompt = (
                f"{user_prompt}\n"
                f"Selected requirement_ids: {', '.join(requirement_ids)}\n"
                "Rules: create at least 1 test case per selected requirement_id.\n"
                "Rules: include labels across output: normal,error,exception.\n"
            )
            if target_case_count in {3, 4, 5}:
                generation_prompt += f"Rules: generate total {target_case_count} test cases.\n"

            cases, review_required = await self._generator.generate(selected, user_prompt=generation_prompt)
            if review_required:
                self._mark_review_required(request_id, requested_by)
                sqlite_store.save_tc_draft(request_id, [])
                sqlite_store.set_review_state(request_id, is_reviewed=False, last_edited_at=None)
                sqlite_store.save_validation(
                    ValidationRecord(
                        request_id=request_id,
                        validated_at=datetime.now(timezone.utc),
                        result=validate_tc_list([], requirement_ids=requirement_ids, target_case_count=target_case_count),
                    )
                )
                return request_id

            validation = validate_tc_list(cases, requirement_ids=requirement_ids, target_case_count=target_case_count)
            if not validation.is_valid and validation.failure_action == "regenerate":
                cases_retry, review_required_retry = await self._generator.generate(
                    selected,
                    user_prompt=generation_prompt,
                )
                if not review_required_retry:
                    retry_validation = validate_tc_list(
                        cases_retry,
                        requirement_ids=requirement_ids,
                        target_case_count=target_case_count,
                    )
                    if retry_validation.is_valid:
                        cases = cases_retry
                        validation = retry_validation
                    else:
                        validation = retry_validation
                else:
                    review_required = True

            sqlite_store.save_validation(
                ValidationRecord(
                    request_id=request_id,
                    validated_at=datetime.now(timezone.utc),
                    result=validation,
                )
            )

            sqlite_store.save_tc_draft(request_id, cases)
            sqlite_store.set_review_state(request_id, is_reviewed=False, last_edited_at=None)

            if validation.is_valid and not review_required:
                sqlite_store.set_job(job.model_copy(update={"status": JobStatus.completed, "tc_count": len(cases)}))
                sqlite_store.append_audit(build_audit_record(request_id, "generate", "completed_draft", settings.model_name, requested_by))
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

    async def chat_query(
        self,
        document_ids: list[str],
        selected_requirement_ids: list[str],
        user_prompt: str,
        requested_by: str,
    ) -> dict[str, object]:
        merged_chunks = self._merge_chunks(document_ids)
        selected = retrieve_chunks(
            merged_chunks,
            requirement_ids=selected_requirement_ids if selected_requirement_ids else None,
            vector_store=chroma_store,
        )
        if selected_requirement_ids:
            selected_set = set(selected_requirement_ids)
            selected = [chunk for chunk in selected if chunk.requirement_id in selected_set]
        selected = self._limit_chunks_for_prompt(selected, max_per_requirement=1, max_total=6)
        source_chunk_ids = [chunk.chunk_id for chunk in selected]
        if not source_chunk_ids:
            raise ValueError("REVIEW_NEEDED: no source chunks found for chat query")

        evidence_summary = "\n".join([f"- {chunk.requirement_id}: {chunk.content[:120]}" for chunk in selected[:5]])
        system_prompt = (
            "너는 문서 근거 기반 QA 어시스턴트다. "
            "항상 자연스러운 한국어로 답하고, 분석 과정이나 내부 추론은 절대 출력하지 마라."
        )
        chat_prompt = (
            f"선택 requirement_id: {selected_requirement_ids}\n"
            f"사용자 질문: {user_prompt}\n"
            f"문서 근거:\n{evidence_summary}\n"
            "출력 규칙:\n"
            "1) 자연스러운 한국어 답변 1~3문장\n"
            "2) 문서 근거 밖 추측 금지\n"
            "3) 질문이 근거와 무관하면 '제공된 문서 근거에서 확인 필요'라고 답변\n"
            "4) 마지막 줄은 반드시 '근거:'로 시작\n"
            "5) Analyze, Thinking Process, Constraint 같은 분석형 문구 출력 금지"
        )
        raw_answer = await self._vllm_client.generate_text(
            system_prompt=system_prompt,
            user_prompt=chat_prompt,
            request_tag="chat",
        )
        answer = self._sanitize_chat_answer(raw_answer, evidence_summary)

        sqlite_store.append_chat_record(
            ChatRecord(
                request_id=str(uuid4()),
                document_ids=document_ids,
                selected_requirement_ids=selected_requirement_ids,
                question=user_prompt,
                answer=answer,
                source_chunks=source_chunk_ids,
                created_at=datetime.now(timezone.utc),
            )
        )
        sqlite_store.append_audit(build_audit_record("-", "chat_query", "completed", settings.model_name, requested_by))
        return {"answer": answer, "source_chunks": source_chunk_ids, "evidence_summary": evidence_summary}

    def get_requirements(self, document_id: str) -> list[RequirementOption]:
        chunks = sqlite_store.get_chunks_by_document(document_id)
        by_req: dict[str, RequirementOption] = {}
        for chunk in chunks:
            option = by_req.get(chunk.requirement_id)
            if option is None:
                by_req[chunk.requirement_id] = RequirementOption(
                    requirement_id=chunk.requirement_id,
                    source_chunks=[chunk.chunk_id],
                    source_doc=chunk.source_doc,
                )
            else:
                option.source_chunks.append(chunk.chunk_id)
        return sorted(by_req.values(), key=lambda item: item.requirement_id)

    def get_validation(self, request_id: str) -> ValidationRecord | None:
        return sqlite_store.get_validation(request_id)

    def get_rtm(self, request_id: str) -> list[RTMRow]:
        review_state = sqlite_store.get_review_state(request_id)
        if review_state is None or not bool(review_state["is_reviewed"]):
            return []
        validation = sqlite_store.get_validation(request_id)
        if validation is None or not validation.result.is_valid:
            return []
        return sqlite_store.get_rtm_rows(request_id)

    def get_tc_draft(self, request_id: str) -> list[TestCase]:
        return sqlite_store.get_tc_draft(request_id)

    def update_tc_draft(self, request_id: str, cases: list[TestCase], requested_by: str) -> ValidationRecord:
        old_cases = sqlite_store.get_tc_draft(request_id)
        sqlite_store.save_tc_draft(request_id, cases)
        edited_at = datetime.now(timezone.utc).isoformat()
        sqlite_store.set_review_state(request_id, is_reviewed=False, last_edited_at=edited_at)
        changed_fields = self._compute_changed_fields(old_cases, cases)
        sqlite_store.append_edit_history(
            EditHistoryRecord(
                request_id=request_id,
                edited_by=requested_by,
                edited_at=datetime.now(timezone.utc),
                changed_fields=changed_fields,
            )
        )
        generation = sqlite_store.get_generation_record(request_id)
        requirement_ids = generation.selected_requirement_ids if generation is not None else []
        target_case_count = generation.target_case_count if generation is not None else None
        validation = ValidationRecord(
            request_id=request_id,
            validated_at=datetime.now(timezone.utc),
            result=validate_tc_list(cases, requirement_ids=requirement_ids, target_case_count=target_case_count),
        )
        sqlite_store.save_validation(validation)
        sqlite_store.append_audit(build_audit_record(request_id, "draft_update", "completed", settings.model_name, requested_by))
        return validation

    def complete_review(self, request_id: str, requested_by: str) -> ValidationRecord:
        draft_cases = sqlite_store.get_tc_draft(request_id)
        sqlite_store.append_edit_history(
            EditHistoryRecord(
                request_id=request_id,
                edited_by=requested_by,
                edited_at=datetime.now(timezone.utc),
                changed_fields=[],
            )
        )
        generation = sqlite_store.get_generation_record(request_id)
        requirement_ids = generation.selected_requirement_ids if generation is not None else []
        target_case_count = generation.target_case_count if generation is not None else None
        validation = ValidationRecord(
            request_id=request_id,
            validated_at=datetime.now(timezone.utc),
            result=validate_tc_list(draft_cases, requirement_ids=requirement_ids, target_case_count=target_case_count),
        )
        sqlite_store.save_validation(validation)
        if not validation.result.is_valid:
            validation.result.failure_action = "wait_user_review"
            sqlite_store.save_validation(validation)
            self._mark_review_required(request_id, requested_by)
            return validation

        sqlite_store.set_review_state(
            request_id=request_id,
            is_reviewed=True,
            last_edited_at=datetime.now(timezone.utc).isoformat(),
        )
        rtm_rows = build_rtm_rows(draft_cases)
        sqlite_store.save_rtm_rows(request_id, rtm_rows)
        export_bytes = build_excel_xlsx(draft_cases, rtm_rows)
        export_path = file_store.save_export_xlsx(request_id=request_id, content=export_bytes)
        sqlite_store.save_export_metadata(
            request_id=request_id,
            file_path=export_path,
            file_format="xlsx",
            size_bytes=len(export_bytes),
        )
        job = sqlite_store.get_job(request_id)
        if job is not None:
            sqlite_store.set_job(job.model_copy(update={"status": JobStatus.completed, "tc_count": len(draft_cases)}))
        sqlite_store.append_audit(build_audit_record(request_id, "review_complete", "completed", settings.model_name, requested_by))
        return validation

    def get_export(self, request_id: str) -> bytes | None:
        review_state = sqlite_store.get_review_state(request_id)
        if review_state is None or not bool(review_state["is_reviewed"]):
            return None
        validation = sqlite_store.get_validation(request_id)
        if validation is None or not validation.result.is_valid:
            return None
        metadata = sqlite_store.get_export_metadata(request_id)
        if metadata is None:
            return None
        return file_store.load_bytes(str(metadata["file_path"]))

    def _merge_chunks(self, document_ids: list[str]) -> list[ChunkMetadata]:
        merged_chunks: list[ChunkMetadata] = []
        for document_id in document_ids:
            merged_chunks.extend(sqlite_store.get_chunks_by_document(document_id))
        return merged_chunks

    def _compute_changed_fields(self, old_cases: list[TestCase], new_cases: list[TestCase]) -> list[str]:
        old_map = {case.tc_id: case.model_dump(mode="json") for case in old_cases}
        changed: set[str] = set()
        for case in new_cases:
            new_payload = case.model_dump(mode="json")
            old_payload = old_map.get(case.tc_id, {})
            for field, value in new_payload.items():
                if old_payload.get(field) != value:
                    changed.add(field)
        return sorted(changed)

    def _limit_chunks_for_prompt(
        self,
        chunks: list[ChunkMetadata],
        max_per_requirement: int,
        max_total: int,
    ) -> list[ChunkMetadata]:
        limited: list[ChunkMetadata] = []
        per_requirement: dict[str, int] = {}
        for chunk in chunks:
            count = per_requirement.get(chunk.requirement_id, 0)
            if count >= max_per_requirement:
                continue
            limited.append(chunk)
            per_requirement[chunk.requirement_id] = count + 1
            if len(limited) >= max_total:
                break
        return limited

    def _sanitize_chat_answer(self, answer: str, evidence_summary: str) -> str:
        cleaned = answer.replace("```", "").strip()
        lowered = cleaned.lower()
        thinking_markers = [
            "thinking process",
            "analyze the request",
            "analysis",
            "constraint",
            "input question",
            "evaluate evidence",
            "step-by-step",
            "chain-of-thought",
            "role:",
        ]
        if any(marker in lowered for marker in thinking_markers):
            lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
            filtered_lines = [line for line in lines if not any(marker in line.lower() for marker in thinking_markers)]
            cleaned = "\n".join(filtered_lines).strip()
        if "근거:" not in cleaned:
            first_evidence = evidence_summary.splitlines()[0].strip() if evidence_summary else "-"
            cleaned = f"{cleaned}\n근거: {first_evidence}".strip()
        has_korean = any("\uac00" <= ch <= "\ud7a3" for ch in cleaned)
        if not has_korean:
            first_evidence = evidence_summary.splitlines()[0].strip() if evidence_summary else "-"
            cleaned = f"제공된 문서 근거에서 확인 필요\n근거: {first_evidence}"
        return cleaned


workflow_service = WorkflowService()

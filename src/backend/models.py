from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    revised = "revised"
    approved = "approved"
    rejected = "rejected"
    check_required = "확인 필요"


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    review_required = "review_required"


class CoverageStatus(str, Enum):
    covered = "covered"
    missing = "missing"
    check_required = "확인 필요"


class ParserOutput(BaseModel):
    document_id: str
    filename: str
    file_type: str
    extracted_text: str
    source_location: str


class NormalizedSection(BaseModel):
    section_title: str
    content: str
    source_location: str


class NormalizedDocument(BaseModel):
    document_id: str
    filename: str
    file_type: str
    sections: list[NormalizedSection]


class ChunkMetadata(BaseModel):
    chunk_id: str
    requirement_id: str
    source_doc: str
    source_location: str
    section_title: str
    chunk_type: str
    content: str


class RequirementOption(BaseModel):
    requirement_id: str
    source_chunks: list[str]
    source_doc: str


class TestCase(BaseModel):
    tc_id: str
    requirement_id: str
    feature_name: str
    preconditions: list[str]
    test_steps: list[str] = Field(min_length=1)
    test_data: list[str]
    expected_result: str
    test_type: str
    priority: str
    labels: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_chunks: list[str]
    review_status: ReviewStatus


class ValidationCheck(BaseModel):
    rule: str
    passed: bool
    message: str | None = None


class ValidationResult(BaseModel):
    is_valid: bool
    checks: list[ValidationCheck]
    failure_action: str


class RTMRow(BaseModel):
    requirement_id: str
    tc_id: str
    coverage_status: CoverageStatus
    duplicate_flag: bool
    source_chunks: list[str]


class JobRecord(BaseModel):
    request_id: str
    status: JobStatus
    created_at: datetime
    document_ids: list[str]
    tc_count: int | None = None


class AuditRecord(BaseModel):
    request_id: str
    action: str
    status: str
    model: str
    requested_by: str
    created_at: datetime


class GenerationRecord(BaseModel):
    request_id: str
    model_version: str
    prompt_version: str
    generated_at: datetime
    selected_requirement_ids: list[str] = Field(default_factory=list)
    target_case_count: int | None = None
    source_chunks: list[str]


class ChatRecord(BaseModel):
    request_id: str
    document_ids: list[str]
    selected_requirement_ids: list[str]
    question: str
    answer: str
    source_chunks: list[str]
    created_at: datetime


class EditHistoryRecord(BaseModel):
    request_id: str
    edited_by: str
    edited_at: datetime
    changed_fields: list[str]


class ValidationRecord(BaseModel):
    request_id: str
    validated_at: datetime
    result: ValidationResult


class ReviewHistoryRecord(BaseModel):
    request_id: str
    status: ReviewStatus
    reviewer: str
    reviewed_at: datetime
    note: str

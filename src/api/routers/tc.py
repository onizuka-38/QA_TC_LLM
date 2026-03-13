from fastapi import APIRouter, HTTPException

from src.api.schemas.tc import (
    DraftCase,
    DraftResponse,
    DraftUpdateRequest,
    GenerateRequest,
    GenerateResponse,
    ReviewCompleteRequest,
)
from src.backend.models import TestCase
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/tc", tags=["tc"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_tc(request: GenerateRequest) -> GenerateResponse:
    try:
        request_id = await workflow_service.generate(
            document_ids=request.document_ids,
            requirement_ids=request.requirement_ids,
            user_prompt=request.user_prompt,
            target_case_count=request.target_case_count,
            requested_by=request.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job = workflow_service.get_job(request_id)
    status = job.status.value if job is not None else "failed"
    return GenerateResponse(request_id=request_id, status=status)


@router.get("/drafts/{request_id}", response_model=DraftResponse)
async def get_tc_draft(request_id: str) -> DraftResponse:
    cases = workflow_service.get_tc_draft(request_id)
    if not cases:
        raise HTTPException(status_code=404, detail="draft not found")
    payload = [DraftCase(**case.model_dump(mode="json")) for case in cases]
    return DraftResponse(request_id=request_id, cases=payload)


@router.put("/drafts/{request_id}", response_model=DraftResponse)
async def update_tc_draft(request_id: str, request: DraftUpdateRequest) -> DraftResponse:
    cases = [TestCase.model_validate(case.model_dump(mode="json")) for case in request.cases]
    workflow_service.update_tc_draft(
        request_id=request_id,
        cases=cases,
        requested_by=request.requested_by,
    )
    refreshed = workflow_service.get_tc_draft(request_id)
    payload = [DraftCase(**case.model_dump(mode="json")) for case in refreshed]
    return DraftResponse(request_id=request_id, cases=payload)


@router.post("/review/{request_id}/complete")
async def complete_review(request_id: str, request: ReviewCompleteRequest) -> GenerateResponse:
    validation = workflow_service.complete_review(request_id=request_id, requested_by=request.requested_by)
    if not validation.result.is_valid:
        raise HTTPException(status_code=409, detail="review complete failed validation")
    job = workflow_service.get_job(request_id)
    status = job.status.value if job is not None else "failed"
    return GenerateResponse(request_id=request_id, status=status)

from fastapi import APIRouter, HTTPException

from src.api.schemas.jobs import JobResponse
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{request_id}", response_model=JobResponse)
async def get_job(request_id: str) -> JobResponse:
    payload = workflow_service.get_job(request_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(**payload.model_dump())

from fastapi import APIRouter

from src.api.schemas.tc import GenerateRequest, GenerateResponse
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/tc", tags=["tc"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_tc(request: GenerateRequest) -> GenerateResponse:
    request_id = await workflow_service.generate(
        document_ids=request.document_ids,
        requirement_ids=request.requirement_ids,
        user_prompt=request.user_prompt,
        requested_by=request.requested_by,
    )
    job = workflow_service.get_job(request_id)
    status = job.status.value if job is not None else "failed"
    return GenerateResponse(request_id=request_id, status=status)

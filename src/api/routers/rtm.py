from fastapi import APIRouter

from src.api.schemas.rtm import RTMResponse, RTMRow
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/rtm", tags=["rtm"])


@router.get("/{request_id}", response_model=RTMResponse)
async def get_rtm(request_id: str) -> RTMResponse:
    rows = workflow_service.get_rtm(request_id)
    payload = [
        RTMRow(
            requirement_id=row.requirement_id,
            tc_id=row.tc_id,
            coverage_status=row.coverage_status.value,
            duplicate_flag=row.duplicate_flag,
            source_chunks=row.source_chunks,
        )
        for row in rows
    ]
    return RTMResponse(request_id=request_id, rows=payload)

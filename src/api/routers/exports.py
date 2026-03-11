from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{request_id}")
async def download_export(request_id: str) -> Response:
    content = workflow_service.get_export(request_id)
    if content is None:
        raise HTTPException(status_code=404, detail="export not found")
    headers = {"Content-Disposition": f"attachment; filename=tc_rtm_{request_id}.xlsx"}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.schemas.documents import UploadResponse, UploadedDocument
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    requested_by: str = Form("system"),
) -> UploadResponse:
    try:
        uploaded = await workflow_service.upload_documents(files=files, requested_by=requested_by)
        documents = [UploadedDocument(**item) for item in uploaded]
        return UploadResponse(documents=documents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

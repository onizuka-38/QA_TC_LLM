from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.schemas.documents import DocumentRequirementsResponse, RequirementItem, UploadResponse, UploadedDocument
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


@router.get("/{document_id}/requirements", response_model=DocumentRequirementsResponse)
async def get_document_requirements(document_id: str) -> DocumentRequirementsResponse:
    requirements = workflow_service.get_requirements(document_id)
    if not requirements:
        raise HTTPException(status_code=404, detail="requirements not found")
    payload = [
        RequirementItem(
            requirement_id=item.requirement_id,
            source_chunks=item.source_chunks,
            source_doc=item.source_doc,
        )
        for item in requirements
    ]
    return DocumentRequirementsResponse(document_id=document_id, requirements=payload)

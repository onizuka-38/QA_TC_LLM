from fastapi import APIRouter, HTTPException

from src.api.schemas.chat import ChatQueryRequest, ChatQueryResponse
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/query", response_model=ChatQueryResponse)
async def query_chat(request: ChatQueryRequest) -> ChatQueryResponse:
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="document_ids required")
    try:
        payload = await workflow_service.chat_query(
            document_ids=request.document_ids,
            selected_requirement_ids=request.selected_requirement_ids,
            user_prompt=request.user_prompt,
            requested_by=request.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    source_chunks_raw = payload.get("source_chunks", [])
    source_chunks = [str(item) for item in source_chunks_raw] if isinstance(source_chunks_raw, list) else []
    return ChatQueryResponse(
        answer=str(payload.get("answer", "")),
        source_chunks=source_chunks,
        evidence_summary=(str(payload["evidence_summary"]) if payload.get("evidence_summary") is not None else None),
    )

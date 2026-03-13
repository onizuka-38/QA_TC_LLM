from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    selected_requirement_ids: list[str] = Field(default_factory=list)
    user_prompt: str
    requested_by: str = "system"


class ChatQueryResponse(BaseModel):
    answer: str
    source_chunks: list[str]
    evidence_summary: str | None = None

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    user_prompt: str = ""
    requested_by: str = "system"


class GenerateResponse(BaseModel):
    request_id: str
    status: str

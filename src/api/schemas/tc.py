from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    user_prompt: str = ""
    target_case_count: int | None = None
    requested_by: str = "system"


class GenerateResponse(BaseModel):
    request_id: str
    status: str


class DraftCase(BaseModel):
    tc_id: str
    requirement_id: str
    feature_name: str
    preconditions: list[str]
    test_steps: list[str]
    test_data: list[str]
    expected_result: str
    test_type: str
    priority: str
    labels: list[str] = Field(default_factory=list)
    notes: str | None = None
    source_chunks: list[str]
    review_status: str


class DraftResponse(BaseModel):
    request_id: str
    cases: list[DraftCase]


class DraftUpdateRequest(BaseModel):
    cases: list[DraftCase]
    requested_by: str = "system"


class ReviewCompleteRequest(BaseModel):
    requested_by: str = "system"

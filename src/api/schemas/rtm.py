from pydantic import BaseModel


class RTMRow(BaseModel):
    requirement_id: str
    tc_id: str
    coverage_status: str
    duplicate_flag: bool
    source_chunks: list[str]


class RTMResponse(BaseModel):
    request_id: str
    rows: list[RTMRow]

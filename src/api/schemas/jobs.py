from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    request_id: str
    status: str
    created_at: datetime | None = None
    document_ids: list[str] | None = None
    tc_count: int | None = None

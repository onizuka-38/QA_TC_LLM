from pydantic import BaseModel


class UploadedDocument(BaseModel):
    document_id: str
    filename: str | None
    file_type: str


class UploadResponse(BaseModel):
    documents: list[UploadedDocument]

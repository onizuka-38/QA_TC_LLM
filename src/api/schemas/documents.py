from pydantic import BaseModel


class UploadedDocument(BaseModel):
    document_id: str
    filename: str | None
    file_type: str


class UploadResponse(BaseModel):
    documents: list[UploadedDocument]


class RequirementItem(BaseModel):
    requirement_id: str
    source_chunks: list[str]
    source_doc: str


class DocumentRequirementsResponse(BaseModel):
    document_id: str
    requirements: list[RequirementItem]

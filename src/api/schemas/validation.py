from pydantic import BaseModel


class ValidationCheck(BaseModel):
    rule: str
    passed: bool
    message: str | None = None


class ValidationResponse(BaseModel):
    request_id: str
    is_valid: bool
    checks: list[ValidationCheck]
    failure_action: str

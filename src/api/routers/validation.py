from fastapi import APIRouter, HTTPException

from src.api.schemas.validation import ValidationCheck, ValidationResponse
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("/{request_id}", response_model=ValidationResponse)
async def get_validation(request_id: str) -> ValidationResponse:
    payload = workflow_service.get_validation(request_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="validation not found")
    checks = [ValidationCheck(rule=check.rule, passed=check.passed) for check in payload.result.checks]
    return ValidationResponse(
        request_id=request_id,
        is_valid=payload.result.is_valid,
        checks=checks,
        failure_action=payload.result.failure_action,
    )

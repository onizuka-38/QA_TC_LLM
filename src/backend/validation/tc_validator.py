from __future__ import annotations

from src.backend.models import TestCase, ValidationCheck, ValidationResult

REQUIRED_FIELDS = [
    "tc_id",
    "requirement_id",
    "feature_name",
    "preconditions",
    "test_steps",
    "test_data",
    "expected_result",
    "test_type",
    "priority",
    "source_chunks",
    "review_status",
]


def validate_tc_list(cases: list[TestCase]) -> ValidationResult:
    checks: list[ValidationCheck] = []
    is_valid = True
    for idx, case in enumerate(cases):
        payload = case.model_dump()
        for field in REQUIRED_FIELDS:
            value = payload[field]
            passed = value not in (None, "", [])
            checks.append(ValidationCheck(rule=f"case[{idx}].{field}_exists", passed=passed))
            if not passed:
                is_valid = False

    return ValidationResult(
        is_valid=is_valid,
        checks=checks,
        failure_action="none" if is_valid else "wait_user_review",
    )

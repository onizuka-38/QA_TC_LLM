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


def validate_tc_list(
    cases: list[TestCase],
    requirement_ids: list[str] | None = None,
    target_case_count: int | None = None,
) -> ValidationResult:
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

    if requirement_ids:
        for requirement_id in requirement_ids:
            covered = any(case.requirement_id == requirement_id for case in cases)
            checks.append(
                ValidationCheck(
                    rule=f"coverage.requirement_id[{requirement_id}]",
                    passed=covered,
                    message=None if covered else f"missing testcase for {requirement_id}",
                )
            )
            if not covered:
                is_valid = False

    if target_case_count in {3, 4, 5}:
        passed_count = len(cases) >= target_case_count
        checks.append(
            ValidationCheck(
                rule=f"coverage.target_case_count[{target_case_count}]",
                passed=passed_count,
                message=None if passed_count else f"generated {len(cases)} < target {target_case_count}",
            )
        )
        if not passed_count:
            is_valid = False

    required_labels = {"normal", "error", "exception"}
    existing_labels = {label.strip().lower() for case in cases for label in case.labels}
    labels_passed = required_labels.issubset(existing_labels)
    checks.append(
        ValidationCheck(
            rule="coverage.labels.normal_error_exception",
            passed=labels_passed,
            message=None if labels_passed else "labels must include normal,error,exception",
        )
    )
    if not labels_passed:
        is_valid = False

    return ValidationResult(
        is_valid=is_valid,
        checks=checks,
        failure_action="none" if is_valid else "regenerate",
    )

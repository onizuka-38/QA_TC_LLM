from __future__ import annotations

from io import BytesIO
from typing import cast

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.backend.models import RTMRow, TestCase


def build_excel_xlsx(cases: list[TestCase], rtm_rows: list[RTMRow]) -> bytes:
    workbook = Workbook()
    tc_sheet = cast(Worksheet, workbook.active)
    tc_sheet.title = "TC"
    rtm_sheet = workbook.create_sheet("RTM")

    tc_sheet.append(
        [
            "Requirement ID",
            "TestCase ID",
            "Title",
            "Test Steps",
            "Test Data",
            "Expected Result",
        ]
    )
    for case in cases:
        tc_sheet.append(
            [
                case.requirement_id,
                case.tc_id,
                case.feature_name,
                "\n".join(case.test_steps),
                "\n".join(case.test_data),
                case.expected_result,
            ]
        )

    rtm_sheet.append(["requirement_id", "tc_id", "coverage_status", "duplicate_flag", "source_chunks"])
    for row in rtm_rows:
        rtm_sheet.append([
            row.requirement_id,
            row.tc_id,
            row.coverage_status.value,
            row.duplicate_flag,
            ",".join(row.source_chunks),
        ])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()

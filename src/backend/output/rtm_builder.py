from __future__ import annotations

from src.backend.models import CoverageStatus, RTMRow, TestCase


def build_rtm_rows(cases: list[TestCase]) -> list[RTMRow]:
    rows: list[RTMRow] = []
    seen_pairs: set[tuple[str, str]] = set()
    for case in cases:
        key = (case.requirement_id, case.tc_id)
        duplicate = key in seen_pairs
        seen_pairs.add(key)
        coverage = CoverageStatus.covered if case.requirement_id else CoverageStatus.missing
        rows.append(
            RTMRow(
                requirement_id=case.requirement_id or "확인 필요",
                tc_id=case.tc_id or "확인 필요",
                coverage_status=coverage,
                duplicate_flag=duplicate,
                source_chunks=case.source_chunks,
            )
        )
    return rows

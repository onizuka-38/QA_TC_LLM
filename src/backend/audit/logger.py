from __future__ import annotations

from datetime import datetime, timezone

from src.backend.models import AuditRecord


def build_audit_record(request_id: str, action: str, status: str, model: str, requested_by: str) -> AuditRecord:
    return AuditRecord(
        request_id=request_id,
        action=action,
        status=status,
        model=model,
        requested_by=requested_by,
        created_at=datetime.now(timezone.utc),
    )

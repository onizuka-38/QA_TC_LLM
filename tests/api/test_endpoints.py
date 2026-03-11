from __future__ import annotations

import unittest

from fastapi import HTTPException

from src.api.routers.documents import upload_documents
from src.api.routers.exports import download_export
from src.api.routers.jobs import get_job
from src.api.routers.rtm import get_rtm
from src.api.routers.tc import generate_tc
from src.api.routers.validation import get_validation
from src.api.schemas.tc import GenerateRequest
from src.backend.services.workflow_service import workflow_service
from tests.test_utils import DummyUploadFile, StubGeneratorReviewRequired, StubGeneratorSuccess, reset_state


class ApiEndpointsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        reset_state()
        self.original_generator = workflow_service._generator

    async def asyncTearDown(self) -> None:
        workflow_service._generator = self.original_generator

    async def test_upload_success_pdf(self) -> None:
        file = DummyUploadFile(filename="req.pdf", content=b"REQ-100 content")
        response = await upload_documents(files=[file], requested_by="qa")
        self.assertEqual(response.documents[0].file_type, "pdf")

    async def test_upload_reject_txt(self) -> None:
        file = DummyUploadFile(filename="req.txt", content=b"REQ-100 content")
        with self.assertRaises(HTTPException):
            await upload_documents(files=[file], requested_by="qa")

    async def test_generate_jobs_validation_rtm_exports_success(self) -> None:
        workflow_service._generator = StubGeneratorSuccess()
        file = DummyUploadFile(filename="req.docx", content=b"REQ-100 content")
        uploaded = await upload_documents(files=[file], requested_by="qa")
        document_id = uploaded.documents[0].document_id

        generated = await generate_tc(
            GenerateRequest(document_ids=[document_id], requirement_ids=["REQ-100"], requested_by="qa")
        )
        request_id = generated.request_id

        job = await get_job(request_id)
        self.assertEqual(job.status, "completed")

        validation = await get_validation(request_id)
        self.assertTrue(validation.is_valid)

        rtm = await get_rtm(request_id)
        self.assertEqual(len(rtm.rows), 1)

        exported = await download_export(request_id)
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(
            exported.media_type,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    async def test_generate_review_required_when_json_failure(self) -> None:
        workflow_service._generator = StubGeneratorReviewRequired()
        file = DummyUploadFile(filename="req.xlsx", content=b"REQ-100 content")
        uploaded = await upload_documents(files=[file], requested_by="qa")
        document_id = uploaded.documents[0].document_id

        generated = await generate_tc(
            GenerateRequest(document_ids=[document_id], requirement_ids=["REQ-100"], requested_by="qa")
        )
        request_id = generated.request_id
        job = await get_job(request_id)
        self.assertEqual(job.status, "review_required")


if __name__ == "__main__":
    unittest.main()

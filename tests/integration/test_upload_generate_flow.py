from __future__ import annotations

import unittest

from src.api.routers.documents import upload_documents
from src.api.routers.jobs import get_job
from src.api.routers.rtm import get_rtm
from src.api.routers.tc import generate_tc
from src.api.routers.validation import get_validation
from src.api.schemas.tc import GenerateRequest
from src.backend.services.workflow_service import workflow_service
from tests.test_utils import DummyUploadFile, StubGeneratorSuccess, reset_state


class IntegrationFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_integration_upload_generate_jobs_validation_rtm_flow(self) -> None:
        reset_state()
        original_generator = workflow_service._generator
        workflow_service._generator = StubGeneratorSuccess()
        try:
            uploaded = await upload_documents(
                files=[DummyUploadFile(filename="req.pdf", content=b"REQ-100 content")],
                requested_by="qa",
            )
            document_id = uploaded.documents[0].document_id

            generated = await generate_tc(
                GenerateRequest(document_ids=[document_id], requirement_ids=["REQ-100"], requested_by="qa")
            )
            request_id = generated.request_id

            self.assertEqual((await get_job(request_id)).status, "completed")
            self.assertTrue((await get_validation(request_id)).is_valid)
            self.assertEqual(len((await get_rtm(request_id)).rows), 1)
        finally:
            workflow_service._generator = original_generator


if __name__ == "__main__":
    unittest.main()

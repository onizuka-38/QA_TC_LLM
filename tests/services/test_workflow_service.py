from __future__ import annotations

import unittest

from src.backend.services.workflow_service import workflow_service
from tests.test_utils import DummyUploadFile, StubGeneratorSuccess, reset_state


class WorkflowServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_success_path(self) -> None:
        reset_state()
        original_generator = workflow_service._generator
        workflow_service._generator = StubGeneratorSuccess()
        try:
            upload = DummyUploadFile(filename="req.pdf", content=b"REQ-100 content")
            docs = await workflow_service.upload_documents([upload], requested_by="qa")
            request_id = await workflow_service.generate(
                [docs[0]["document_id"]],
                ["REQ-100"],
                "REQ-100 테스트케이스 생성",
                "qa",
            )

            job = workflow_service.get_job(request_id)
            validation = workflow_service.get_validation(request_id)
            rtm = workflow_service.get_rtm(request_id)
            exported = workflow_service.get_export(request_id)

            self.assertIsNotNone(job)
            self.assertEqual(job.status.value, "completed")
            self.assertIsNotNone(validation)
            self.assertTrue(validation.result.is_valid)
            self.assertEqual(len(rtm), 1)
            self.assertIsNotNone(exported)
            self.assertTrue(exported.startswith(b"PK"))
        finally:
            workflow_service._generator = original_generator


if __name__ == "__main__":
    unittest.main()

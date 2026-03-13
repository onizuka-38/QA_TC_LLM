from __future__ import annotations

import unittest

from src.backend.services.workflow_service import workflow_service
from src.backend.storage.sqlite_store import sqlite_store
from tests.test_utils import DummyUploadFile, StubChatClient, StubGeneratorSuccess, reset_state


class WorkflowServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_workflow_success_path(self) -> None:
        reset_state()
        original_generator = workflow_service._generator
        original_chat_client = workflow_service._vllm_client
        workflow_service._generator = StubGeneratorSuccess()
        workflow_service._vllm_client = StubChatClient()
        try:
            upload = DummyUploadFile(filename="req.pdf", content=b"REQ-100 content")
            docs = await workflow_service.upload_documents([upload], requested_by="qa")
            request_id = await workflow_service.generate(
                [docs[0]["document_id"]],
                ["REQ-100"],
                "REQ-100 테스트케이스 생성",
                None,
                "qa",
            )

            job = workflow_service.get_job(request_id)
            validation = workflow_service.get_validation(request_id)
            rtm = workflow_service.get_rtm(request_id)
            exported = workflow_service.get_export(request_id)
            workflow_service.complete_review(request_id, "qa")
            rtm_after_review = workflow_service.get_rtm(request_id)
            exported_after_review = workflow_service.get_export(request_id)
            generation_record = sqlite_store.get_generation_record(request_id)
            chat = await workflow_service.chat_query(
                document_ids=[docs[0]["document_id"]],
                selected_requirement_ids=["REQ-100"],
                user_prompt="REQ-100 설명",
                requested_by="qa",
            )
            latest_chat = sqlite_store.get_latest_chat_record()
            latest_edit = sqlite_store.get_latest_edit_history(request_id)

            self.assertIsNotNone(job)
            self.assertEqual(job.status.value, "completed")
            self.assertIsNotNone(validation)
            self.assertTrue(validation.result.is_valid)
            self.assertEqual(len(rtm), 0)
            self.assertIsNone(exported)
            self.assertEqual(len(rtm_after_review), 1)
            self.assertIsNotNone(exported_after_review)
            self.assertTrue(exported_after_review.startswith(b"PK"))
            self.assertIsNotNone(generation_record)
            self.assertEqual(generation_record.selected_requirement_ids, ["REQ-100"])
            self.assertTrue(generation_record.source_chunks)
            self.assertTrue(chat["source_chunks"])
            self.assertIsNotNone(latest_chat)
            self.assertEqual(latest_chat.question, "REQ-100 설명")
            self.assertTrue(latest_chat.source_chunks)
            self.assertIsNotNone(latest_edit)
            self.assertEqual(latest_edit.edited_by, "qa")
        finally:
            workflow_service._generator = original_generator
            workflow_service._vllm_client = original_chat_client


if __name__ == "__main__":
    unittest.main()

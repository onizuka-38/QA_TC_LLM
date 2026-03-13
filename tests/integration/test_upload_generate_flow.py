from __future__ import annotations

import unittest

from src.api.routers.chat import query_chat
from src.api.routers.documents import get_document_requirements, upload_documents
from src.api.routers.exports import download_export
from src.api.routers.jobs import get_job
from src.api.routers.rtm import get_rtm
from src.api.routers.tc import complete_review, generate_tc, get_tc_draft, update_tc_draft
from src.api.routers.validation import get_validation
from src.api.schemas.chat import ChatQueryRequest
from src.api.schemas.tc import DraftUpdateRequest, GenerateRequest, ReviewCompleteRequest
from src.backend.services.workflow_service import workflow_service
from tests.test_utils import DummyUploadFile, StubChatClient, StubGeneratorSuccess, reset_state


class IntegrationFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_integration_upload_requirements_chat_generate_review_validate_rtm_export(self) -> None:
        reset_state()
        original_generator = workflow_service._generator
        original_chat_client = workflow_service._vllm_client
        workflow_service._generator = StubGeneratorSuccess()
        workflow_service._vllm_client = StubChatClient()
        try:
            uploaded = await upload_documents(
                files=[DummyUploadFile(filename="req.pdf", content=b"REQ-100 content REQ-101 content REQ-102 content")],
                requested_by="qa",
            )
            document_id = uploaded.documents[0].document_id

            requirements = await get_document_requirements(document_id)
            selected_ids = [row.requirement_id for row in requirements.requirements if row.requirement_id in {"REQ-100"}]

            chat = await query_chat(
                ChatQueryRequest(
                    document_ids=[document_id],
                    selected_requirement_ids=selected_ids,
                    user_prompt="REQ-100 요약해줘",
                    requested_by="qa",
                )
            )
            self.assertTrue(chat.source_chunks)

            generated = await generate_tc(
                GenerateRequest(
                    document_ids=[document_id],
                    requirement_ids=selected_ids,
                    user_prompt="선택 requirement 중심으로 생성",
                    target_case_count=None,
                    requested_by="qa",
                )
            )
            request_id = generated.request_id

            draft = await get_tc_draft(request_id)
            await update_tc_draft(
                request_id,
                DraftUpdateRequest(cases=draft.cases, requested_by="qa"),
            )

            await complete_review(request_id, ReviewCompleteRequest(requested_by="qa"))

            self.assertEqual((await get_job(request_id)).status, "completed")
            self.assertTrue((await get_validation(request_id)).is_valid)
            self.assertEqual(len((await get_rtm(request_id)).rows), 1)
            exported = await download_export(request_id)
            self.assertEqual(exported.status_code, 200)
        finally:
            workflow_service._generator = original_generator
            workflow_service._vllm_client = original_chat_client


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from fastapi import HTTPException

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
from src.backend.storage.sqlite_store import sqlite_store
from tests.test_utils import DummyUploadFile, StubChatClient, StubGeneratorReviewRequired, StubGeneratorSuccess, reset_state


class ApiEndpointsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        reset_state()
        self.original_generator = workflow_service._generator
        self.original_chat_client = workflow_service._vllm_client
        workflow_service._vllm_client = StubChatClient()

    async def asyncTearDown(self) -> None:
        workflow_service._generator = self.original_generator
        workflow_service._vllm_client = self.original_chat_client

    async def test_upload_success_pdf(self) -> None:
        file = DummyUploadFile(filename="req.pdf", content=b"REQ-100 content")
        response = await upload_documents(files=[file], requested_by="qa")
        self.assertEqual(response.documents[0].file_type, "pdf")

    async def test_upload_reject_txt(self) -> None:
        file = DummyUploadFile(filename="req.txt", content=b"REQ-100 content")
        with self.assertRaises(HTTPException):
            await upload_documents(files=[file], requested_by="qa")

    async def test_requirements_api_success(self) -> None:
        file = DummyUploadFile(filename="req.pdf", content=b"REQ-100 content REQ-101 content")
        uploaded = await upload_documents(files=[file], requested_by="qa")
        response = await get_document_requirements(uploaded.documents[0].document_id)
        self.assertGreaterEqual(len(response.requirements), 2)

    async def test_chat_query_success(self) -> None:
        file = DummyUploadFile(filename="req.pdf", content=b"REQ-100 content REQ-101 content")
        uploaded = await upload_documents(files=[file], requested_by="qa")
        document_id = uploaded.documents[0].document_id
        response = await query_chat(
            ChatQueryRequest(
                document_ids=[document_id],
                selected_requirement_ids=["REQ-100"],
                user_prompt="REQ-100 설명해줘",
                requested_by="qa",
            )
        )
        self.assertTrue(response.source_chunks)
        self.assertIn("문서 근거", response.answer)
        self.assertIn("REQ-100", response.evidence_summary or "")
        chunks = sqlite_store.get_chunks_by_document(document_id)
        by_chunk = {chunk.chunk_id: chunk.requirement_id for chunk in chunks}
        self.assertTrue(all(by_chunk.get(chunk_id) == "REQ-100" for chunk_id in response.source_chunks))

    async def test_chat_query_review_needed_without_evidence(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await query_chat(
                ChatQueryRequest(
                    document_ids=["missing-doc"],
                    selected_requirement_ids=["REQ-100"],
                    user_prompt="질문",
                    requested_by="qa",
                )
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("REVIEW_NEEDED", str(ctx.exception.detail))

    async def test_generate_review_complete_export_flow(self) -> None:
        workflow_service._generator = StubGeneratorSuccess()
        file = DummyUploadFile(filename="req.docx", content=b"REQ-100 content")
        uploaded = await upload_documents(files=[file], requested_by="qa")
        document_id = uploaded.documents[0].document_id

        generated = await generate_tc(
            GenerateRequest(
                document_ids=[document_id],
                requirement_ids=["REQ-100"],
                user_prompt="REQ-100 생성",
                requested_by="qa",
            )
        )
        request_id = generated.request_id

        with self.assertRaises(HTTPException) as export_before_review:
            await download_export(request_id)
        self.assertEqual(export_before_review.exception.status_code, 404)

        draft = await get_tc_draft(request_id)
        self.assertEqual(len(draft.cases), 1)

        await update_tc_draft(
            request_id,
            DraftUpdateRequest(cases=draft.cases, requested_by="qa"),
        )

        await complete_review(request_id, ReviewCompleteRequest(requested_by="qa"))

        job = await get_job(request_id)
        self.assertEqual(job.status, "completed")
        validation = await get_validation(request_id)
        self.assertTrue(validation.is_valid)
        rtm = await get_rtm(request_id)
        self.assertEqual(len(rtm.rows), 1)
        exported = await download_export(request_id)
        self.assertEqual(exported.status_code, 200)

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

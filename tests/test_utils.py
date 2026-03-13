from __future__ import annotations

from src.backend.models import ReviewStatus, TestCase
from src.backend.retrieval.chroma_store import chroma_store
from src.backend.storage.file_store import file_store
from src.backend.storage.sqlite_store import sqlite_store


class DummyUploadFile:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


class StubGeneratorSuccess:
    async def generate(self, chunks, user_prompt: str = ""):
        cases = [
            TestCase(
                tc_id="TC-001",
                requirement_id="REQ-100",
                feature_name="login",
                preconditions=["user exists"],
                test_steps=["open login", "submit"],
                test_data=["id=pw"],
                expected_result="login success",
                test_type="normal",
                priority="high",
                labels=["normal", "error", "exception"],
                source_chunks=[chunks[0].chunk_id] if chunks else ["chunk-none"],
                review_status=ReviewStatus.draft,
            )
        ]
        return cases, False


class StubGeneratorReviewRequired:
    async def generate(self, chunks, user_prompt: str = ""):
        return [], True


class StubChatClient:
    async def generate_text(self, system_prompt: str, user_prompt: str, request_tag: str = "") -> str:
        return "문서 근거 기반 답변입니다."


def reset_state() -> None:
    sqlite_store.clear_all()
    chroma_store.clear()
    file_store.clear_all()

from __future__ import annotations

import json
import re
from hashlib import sha1

from pydantic import ValidationError

from src.backend.generation.vllm_client import VLLMClient
from src.backend.models import ChunkMetadata, TestCase
from src.core.config import settings


class TCGenerator:
    def __init__(self, vllm_client: VLLMClient | None = None) -> None:
        self.vllm_client = vllm_client or VLLMClient()

    async def generate(self, chunks: list[ChunkMetadata], user_prompt: str = "") -> tuple[list[TestCase], bool]:
        prompt = self._build_prompt(chunks, user_prompt)
        request_tag = sha1(prompt.encode("utf-8")).hexdigest()[:16]
        attempts = settings.generation_retry_count + 1
        for attempt in range(attempts):
            try:
                raw = await self.vllm_client.generate_json(prompt, request_tag=request_tag)
                json_text = self._extract_json_text(raw)
                parsed = json.loads(json_text)
                items = parsed if isinstance(parsed, list) else [parsed]
                cases = [TestCase.model_validate(item) for item in items]
                return cases, False
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
                if attempt == attempts - 1:
                    return [], True
            except Exception:
                if attempt == attempts - 1:
                    return [], True
        return [], True

    def _build_prompt(self, chunks: list[ChunkMetadata], user_prompt: str) -> str:
        evidence = [chunk.model_dump() for chunk in chunks]
        return (
            "Generate JSON array of test cases with fields: "
            "tc_id, requirement_id, feature_name, preconditions, test_steps, "
            "test_data, expected_result, test_type, priority, source_chunks, review_status. "
            f"User prompt: {user_prompt}. "
            f"Evidence chunks: {evidence}"
        )

    def _extract_json_text(self, raw: str) -> str:
        fenced = re.search(r"```json\\s*(.*?)\\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1)

        # Remove optional reasoning tags.
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()

        start_arr = cleaned.find("[")
        end_arr = cleaned.rfind("]")
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            return cleaned[start_arr : end_arr + 1]

        start_obj = cleaned.find("{")
        end_obj = cleaned.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            return cleaned[start_obj : end_obj + 1]

        return cleaned

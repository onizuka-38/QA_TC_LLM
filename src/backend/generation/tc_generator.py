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
                normalized_items = [self._normalize_case_payload(item) for item in items]
                cases = [TestCase.model_validate(item) for item in normalized_items]
                return cases, False
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
                if attempt == attempts - 1:
                    return [], True
            except Exception:
                if attempt == attempts - 1:
                    return [], True
        return [], True

    def _build_prompt(self, chunks: list[ChunkMetadata], user_prompt: str) -> str:
        compact_chunks = chunks[:8]
        evidence = [
            {
                "chunk_id": chunk.chunk_id,
                "requirement_id": chunk.requirement_id,
                "source_doc": chunk.source_doc,
                "content": chunk.content[:260],
            }
            for chunk in compact_chunks
        ]
        return (
            "Generate ONLY a valid JSON array. "
            "No prose, no markdown, no code fences. "
            "Each item must include fields: "
            "tc_id, requirement_id, feature_name, preconditions, test_steps, "
            "test_data, expected_result, test_type, priority, source_chunks, review_status. "
            "Optional fields: labels(list[str]), notes(string). "
            "Type constraints: preconditions=list[str], test_steps=list[str], test_data=list[str]. "
            "review_status must be exactly 'draft'. "
            "Do not return a single object when multiple requirement_ids are provided. "
            f"User prompt: {user_prompt}. "
            f"Evidence chunks: {evidence}"
        )

    def _extract_json_text(self, raw: str) -> str:
        fenced = re.search(r"```json\\s*(.*?)\\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1)

        # Remove optional reasoning tags.
        cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()

        # Prefer full object when response is a single JSON object containing list fields.
        if cleaned.startswith("{") and cleaned.endswith("}"):
            return cleaned

        if cleaned.startswith("[") and cleaned.endswith("]"):
            return cleaned

        start_arr = cleaned.find("[")
        end_arr = cleaned.rfind("]")
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            return cleaned[start_arr : end_arr + 1]

        start_obj = cleaned.find("{")
        end_obj = cleaned.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            return cleaned[start_obj : end_obj + 1]

        return cleaned

    def _normalize_case_payload(self, item: object) -> object:
        if not isinstance(item, dict):
            return item

        normalized = dict(item)

        preconditions = normalized.get("preconditions")
        if isinstance(preconditions, str):
            normalized["preconditions"] = [preconditions]

        test_steps = normalized.get("test_steps")
        if isinstance(test_steps, str):
            normalized["test_steps"] = [test_steps]

        test_data = normalized.get("test_data")
        if isinstance(test_data, dict):
            normalized["test_data"] = [f"{key}={value}" for key, value in test_data.items()]
        elif isinstance(test_data, str):
            normalized["test_data"] = [test_data]

        review_status = normalized.get("review_status")
        if isinstance(review_status, str) and review_status.lower() == "pending":
            normalized["review_status"] = "draft"

        labels = normalized.get("labels")
        if isinstance(labels, str):
            normalized["labels"] = [labels]

        return normalized

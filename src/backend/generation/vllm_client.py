from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.core.config import settings


class VLLMClient:
    async def generate_json(self, prompt: str, request_tag: str = "") -> str:
        payload = {
            "model": settings.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return ONLY valid JSON array. "
                        "Do not include thinking text, markdown, code fences, or explanations."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {settings.vllm_api_key}"}
        debug_path = Path("data") / "vllm_debug.jsonl"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=settings.generation_timeout_sec) as client:
            try:
                response = await client.post(
                    f"{settings.vllm_base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                raw_content = data["choices"][0]["message"]["content"]
                debug_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_tag": request_tag,
                    "payload": payload,
                    "raw_response": data,
                    "raw_content": raw_content,
                    "error": None,
                }
                with debug_path.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(debug_entry, ensure_ascii=False) + "\n")
                return raw_content
            except Exception as exc:
                debug_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_tag": request_tag,
                    "payload": payload,
                    "raw_response": None,
                    "raw_content": None,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
                with debug_path.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(debug_entry, ensure_ascii=False) + "\n")
                raise

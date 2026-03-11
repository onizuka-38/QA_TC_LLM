from __future__ import annotations

from src.backend.models import ParserOutput


class BaseParser:
    file_type: str = "unsupported"

    def parse(self, document_id: str, filename: str, content: bytes) -> ParserOutput:
        text = content.decode("utf-8", errors="ignore")
        return ParserOutput(
            document_id=document_id,
            filename=filename,
            file_type=self.file_type,
            extracted_text=text,
            source_location="n/a",
        )

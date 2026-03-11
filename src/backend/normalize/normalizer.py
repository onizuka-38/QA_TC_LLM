from __future__ import annotations

from src.backend.models import NormalizedDocument, NormalizedSection, ParserOutput


def normalize_document(parser_output: ParserOutput) -> NormalizedDocument:
    section = NormalizedSection(
        section_title="full_text",
        content=parser_output.extracted_text,
        source_location=parser_output.source_location,
    )
    return NormalizedDocument(
        document_id=parser_output.document_id,
        filename=parser_output.filename,
        file_type=parser_output.file_type,
        sections=[section],
    )

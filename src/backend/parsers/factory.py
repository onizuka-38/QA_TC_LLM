from __future__ import annotations

from .base import BaseParser
from .excel_parser import ExcelParser
from .pdf_parser import PDFParser
from .word_parser import WordParser


class ParserFactory:
    _mapping = {
        "pdf": PDFParser(),
        "docx": WordParser(),
        "xlsx": ExcelParser(),
    }

    @classmethod
    def resolve(cls, file_ext: str) -> BaseParser:
        return cls._mapping.get(file_ext.lower(), BaseParser())

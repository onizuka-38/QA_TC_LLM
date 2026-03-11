from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.core.config import settings


class FileStore:
    def __init__(self) -> None:
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        settings.exports_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, document_id: str, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix
        path = settings.uploads_dir / f"{document_id}{suffix}"
        path.write_bytes(content)
        return str(path)

    def save_export_xlsx(self, request_id: str, content: bytes) -> str:
        path = settings.exports_dir / f"tc_rtm_{request_id}_{uuid4().hex[:8]}.xlsx"
        path.write_bytes(content)
        return str(path)

    def load_bytes(self, file_path: str) -> bytes:
        return Path(file_path).read_bytes()

    def clear_all(self) -> None:
        for base in (settings.uploads_dir, settings.exports_dir):
            if base.exists():
                for child in base.glob("**/*"):
                    if child.is_file():
                        child.unlink()


file_store = FileStore()

from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "qa-tc-automation"
    model_name: str = "Qwen3.5-27B-GPTQ-Int4"
    vllm_base_url: str = "http://127.0.0.1:8001"
    vllm_api_key: str = "local"
    generation_timeout_sec: float = 240.0
    generation_retry_count: int = 1
    max_concurrent_jobs: int = 5
    vllm_debug_log_enabled: bool = False

    data_dir: Path = Path("data")
    sqlite_path: Path = Path("data/app.db")
    chroma_path: Path = Path("data/chroma")
    uploads_dir: Path = Path("data/uploads")
    exports_dir: Path = Path("data/exports")


settings = Settings()

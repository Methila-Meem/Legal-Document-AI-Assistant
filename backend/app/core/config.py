from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR.parent


class Settings(BaseSettings):
    app_name: str = "Legal Document AI Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_prefix: str = "/api"

    database_url: str = Field(default=f"sqlite:///{BACKEND_DIR / 'app.db'}")
    storage_dir: Path = Field(default=BACKEND_DIR / "storage")
    max_upload_size_mb: int = 25
    allowed_upload_extensions_raw: str = Field(
        default="pdf,png,jpg,jpeg,txt",
        alias="ALLOWED_UPLOAD_EXTENSIONS",
    )
    ocr_engine: str = "easyocr"
    ocr_lang: str = "en"
    ocr_confidence_threshold: float = 0.60
    tesseract_cmd: str | None = Field(default=None, alias="TESSERACT_CMD")

    github_models_api_key: str | None = Field(default=None, alias="GITHUB_MODELS_API_KEY")
    github_models_endpoint: str = "https://models.github.ai/inference/chat/completions"
    github_models_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_collection_name: str = "legal_document_chunks"
    chunk_target_chars: int = 900
    chunk_overlap_chars: int = 150

    frontend_url: str = "http://localhost:3000"
    allowed_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="ALLOWED_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def sqlite_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            configured_path = Path(self.database_url.replace("sqlite:///", "", 1))
            if not configured_path.is_absolute():
                return BACKEND_DIR / configured_path
            return configured_path
        return BACKEND_DIR / "app.db"

    @property
    def resolved_storage_dir(self) -> Path:
        if self.storage_dir.is_absolute():
            return self.storage_dir
        return BACKEND_DIR / self.storage_dir

    @property
    def allowed_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.allowed_origins_raw.split(",")]
        return [origin for origin in origins if origin]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_upload_extensions(self) -> set[str]:
        extensions = {
            extension.strip().lower().lstrip(".")
            for extension in self.allowed_upload_extensions_raw.split(",")
        }
        return {extension for extension in extensions if extension}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

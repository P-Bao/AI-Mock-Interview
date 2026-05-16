from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_atlas_uri: str = Field(alias="MONGODB_ATLAS_URI")
    mongodb_db_name: str = Field(default="cv_interview_app", alias="MONGODB_DB_NAME")

    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.1-flash-lite-preview", alias="GEMINI_MODEL")

    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    mineru_model_source: Literal["huggingface", "modelscope", "local"] = Field(
        default="huggingface", alias="MINERU_MODEL_SOURCE"
    )
    mineru_backend: Literal[
        "pipeline",
        "vlm",
        "vlm-auto-engine",
        "vlm-http-client",
        "hybrid-auto-engine",
        "hybrid-http-client",
    ] = Field(default="pipeline", alias="MINERU_BACKEND")

    kg_enabled: bool = Field(default=True, alias="KG_ENABLED")
    kg_mode: Literal["disabled", "auto", "heuristic", "model", "graph"] = Field(
        default="auto", alias="KG_MODE"
    )
    kg_match_model_path: str = Field(default="", alias="KG_MATCH_MODEL_PATH")
    kg_artifact_dir: str = Field(default="./data/tinix_kg", alias="KG_ARTIFACT_DIR")
    kg_timeout_seconds: int = Field(default=10, alias="KG_TIMEOUT_SECONDS")

    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")
    max_questions: int = Field(default=20, alias="MAX_QUESTIONS")
    task_ttl_seconds: int = Field(default=3600, alias="TASK_TTL_SECONDS")
    eval_max_retries: int = Field(default=3, alias="EVAL_MAX_RETRIES")
    eval_timeout_seconds: int = Field(default=90, alias="EVAL_TIMEOUT_SECONDS")
    mineru_timeout_seconds: int = Field(default=300, alias="MINERU_TIMEOUT_SECONDS")
    mineru_warmup_enabled: bool = Field(default=True, alias="MINERU_WARMUP_ENABLED")
    mineru_warmup_timeout_seconds: int = Field(default=600, alias="MINERU_WARMUP_TIMEOUT_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_atlas_uri: str = Field(alias="MONGODB_ATLAS_URI")
    mongodb_db_name: str = Field(default="cv_interview_app", alias="MONGODB_DB_NAME")

    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    eval_max_retries: int = Field(default=3, alias="EVAL_MAX_RETRIES")
    eval_timeout_seconds: int = Field(default=90, alias="EVAL_TIMEOUT_SECONDS")
    task_ttl_seconds: int = Field(default=3600, alias="TASK_TTL_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

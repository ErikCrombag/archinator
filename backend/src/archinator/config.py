from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.3", alias="OLLAMA_MODEL")
    db_path: str = Field(default="data/archinator.db", alias="DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_key_header: str = Field(default="X-API-Key", alias="API_KEY_HEADER")


settings = Settings()

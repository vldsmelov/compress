from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    ollama_base_url: str = Field(
        # default="http://ollama_ext:11434",
        default="http://ollama:11434",
        description="Базовый URL Ollama",
        alias="OLLAMA_BASE_URL",
    )
    ollama_model: str = Field(
        default="qwen3:14b",
        description="Имя модели Ollama",
        alias="OLLAMA_MODEL",
    )
    ollama_timeout: float = Field(
        default=120.0,
        description="Таймаут запросов к Ollama в секундах",
        alias="OLLAMA_TIMEOUT",
    )
    ollama_num_ctx: int | None = Field(
        default=None,
        description="Размер контекста модели",
        alias="OLLAMA_NUM_CTX",
    )
    cors_allow_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Список доменов, которым разрешен доступ",
        alias="CORS_ALLOW_ORIGINS",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
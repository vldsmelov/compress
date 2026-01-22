from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration for the AI Accountant service."""

    ollama_base_url: str = Field(
        default="http://ollama:11434",
        alias="OLLAMA_BASE_URL",
        description="Base URL for the Ollama instance",
    )
    ollama_model: str = Field(
        default="qwen3:14b-8k",
        alias="OLLAMA_MODEL",
        description="Model identifier to use for analysis",
    )
    ollama_timeout: float = Field(
        default=120.0,
        alias="OLLAMA_TIMEOUT",
        description="HTTP timeout in seconds for Ollama requests",
    )
    ollama_num_ctx: Optional[int] = Field(
        default=None,
        alias="OLLAMA_NUM_CTX",
        description="Optional context window size override",
    )

    cors_allow_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        alias="CORS_ALLOW_ORIGINS",
        description="Allowed origins for CORS middleware",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def ollama_chat_url(self) -> str:
        return f"{self.ollama_base_url.rstrip('/')}/api/chat"

    @property
    def ollama_tags_url(self) -> str:
        return f"{self.ollama_base_url.rstrip('/')}/api/tags"

    def model_post_init(self, __context: object) -> None:  # type: ignore[override]
        if self.ollama_num_ctx is None and self.ollama_model.startswith("qwen3:14b-8k"):
            object.__setattr__(self, "ollama_num_ctx", 65_536)


@lru_cache
def get_settings() -> Settings:
    return Settings()
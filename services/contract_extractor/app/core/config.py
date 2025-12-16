from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed configuration for the Contract Extractor service."""

    app_name: str = Field(default="contract-extractor-api", alias="APP_NAME")
    version: str = Field(default="0.1.0", alias="APP_VERSION")
    env: str = Field(default="dev", alias="ENV")

    ollama_host: str = Field(
        default="http://192.168.3.63:11434",
        alias="OLLAMA_HOST",
        description="Base URL of the Ollama instance",
    )
    model_name: str = Field(
        default="qwen3:14b-8k",
        alias="OLLAMA_MODEL",
        description="Model identifier to use for QA prompts",
    )
    num_ctx: Optional[int] = Field(
        default=None, alias="OLLAMA_NUM_CTX", description="Optional context window override"
    )
    temperature: float = Field(default=0.1, alias="TEMPERATURE")
    max_tokens: int = Field(default=1024, alias="MAX_TOKENS")
    numeric_tolerance: float = Field(default=0.01, alias="NUMERIC_TOLERANCE")
    use_llm: bool = Field(default=True, alias="USE_LLM")
    ollama_read_timeout: float = Field(default=300.0, alias="OLLAMA_READ_TIMEOUT")
    supported_languages: List[str] = Field(
        default_factory=lambda: ["ru", "en"], alias="SUPPORTED_LANGUAGES"
    )

    qa_plans_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
        / "assets"
        / "qa_plans",
        description="Directory with JSON files describing QA plans",
    )
    qa_system_prompt: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
        / "prompts"
        / "qa_system.txt",
        description="Path to the system prompt template",
    )
    qa_user_template: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
        / "prompts"
        / "qa_user_template.txt",
        description="Path to the user prompt template",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def model_post_init(self, __context: object) -> None:  # type: ignore[override]
        if self.num_ctx is None and self.model_name.startswith("qwen3:14b-8k"):
            object.__setattr__(self, "num_ctx", 65_536)


@lru_cache
def get_settings() -> Settings:
    return Settings()


__all__ = ["Settings", "get_settings"]

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Centralized configuration for the ai_econom service and its Ollama client."""
    ollama_host: str = Field(default="ollama", alias="OLLAMA_HOST")
    ollama_port: str = Field(default="11434", alias="OLLAMA_PORT")
    ollama_model: str = Field(default="qwen3:14b-8k", alias="OLLAMA_MODEL")
    ollama_temperature: float = Field(default=0.1, alias="OLLAMA_TEMPERATURE")
    ollama_max_tokens: int = Field(default=2000, alias="OLLAMA_MAX_TOKENS")
    ollama_timeout: float = Field(default=60.0, alias="OLLAMA_TIMEOUT")
    ollama_num_ctx: Optional[int] = Field(default=None, alias="OLLAMA_NUM_CTX")

    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data",
        alias="DATA_DIR",
    )
    budget_filename: str = Field(default="budget.json", alias="BUDGET_FILENAME")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def budget_path(self) -> Path:
        return self.data_dir / self.budget_filename

    @property
    def ollama_url(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}/api/chat"

    def model_post_init(self, __context: object) -> None:  # type: ignore[override]
        if self.ollama_num_ctx is None and self.ollama_model.startswith("qwen3:14b-8k"):
            object.__setattr__(self, "ollama_num_ctx", 65_536)


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration for budget storage service."""

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


@lru_cache
def get_settings() -> Settings:
    return Settings()

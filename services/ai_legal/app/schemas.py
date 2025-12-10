from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class LlmDebugInfo(BaseModel):
    prompt: List[dict[str, str]] = Field(..., description="JSON-представление промпта")
    prompt_formatted: str = Field(..., description="Отформатированный промпт")
    response: dict[str, Any] = Field(..., description="Полный ответ модели")
    response_formatted: str = Field(..., description="Ответ модели с отступами")


class SectionReview(BaseModel):
    number: Optional[int] = Field(default=None, description="Порядковый номер раздела")
    title: str = Field(..., description="Название раздела")
    resume: str = Field(..., description="Краткое резюме раздела")
    risks: str = Field(..., description="Перечень рисков по разделу")
    score: str = Field(..., description="Оценка соответствия раздела")


class SectionReviewResponse(BaseModel):
    reviews: List[SectionReview] = Field(..., description="Разбор каждого раздела")
    overall_score: Optional[float] = Field(
        default=None, description="Средняя оценка по всем разделам"
    )
    inaccuracy: Optional[str] = Field(
        default=None, description="Ключевые неточности по документу"
    )
    red_flags: Optional[str] = Field(
        default=None, description="Серьезные ошибки по документу"
    )
    html: str = Field(..., description="HTML-страница со сводкой по разделам")
    debug: Optional[LlmDebugInfo] = Field(
        default=None, description="Отладочная информация с промптом и ответом"
    )


class FullProcessingResponse(BaseModel):
    overall_score: Optional[float] = Field(
        default=None, description="Средняя оценка по всем разделам"
    )
    html: str = Field(..., description="HTML-страница со сводкой по разделам")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Текущее состояние API")
    model: str = Field(..., description="Модель Ollama, которую использует сервис")
    ollama: str = Field(..., description="Базовый URL Ollama, к которому идет обращение")
    model_available: bool = Field(..., description="Модель загружена в Ollama")
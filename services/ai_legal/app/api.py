from __future__ import annotations

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from .config import get_settings
from .llm_client import client
from .pipeline import pipeline
from .reviews import reviewer
from .schemas import FullProcessingResponse, HealthResponse

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Verify Ollama availability and return the configured model name."""
    settings = get_settings()
    models_raw = await client.list_models()
    available = [item.get("name") for item in models_raw.get("models", [])]
    return HealthResponse(
        status="ok",
        model=settings.ollama_model,
        ollama=settings.ollama_base_url,
        model_available=settings.ollama_model in available,
    )


@router.post(
    "/full-prepared",
    response_model=FullProcessingResponse,
    response_model_exclude_none=True,
)
async def review_prepared_sections(
    file: UploadFile = File(...),
) -> FullProcessingResponse:
    """Process a pre-generated sections file produced by document_slicer."""
    try:
        raw_payload = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - defensive decoding
        raise HTTPException(status_code=400, detail="Не удалось прочитать файл как UTF-8") from exc

    if not raw_payload.strip():
        raise HTTPException(status_code=400, detail="Файл с секциями пуст")

    prepared = pipeline.prepare_from_text(raw_payload)
    result = await reviewer.evaluate_sections(
        prepared.combined_text,
        prepared.document_html,
        expected_titles=prepared.titles,
        expected_numbers=prepared.numbers,
    )

    return FullProcessingResponse(
        overall_score=result.overall_score,
        html=result.html_report,
    )


@router.post(
    "/full",
    response_model=FullProcessingResponse,
    response_model_exclude_none=True,
    response_model_exclude={"sections"},
)
async def review_full(
    payload: dict[str, str] = Body(...),
) -> FullProcessingResponse:
    """Process an inline sections payload and return rendered legal review results."""
    prepared = pipeline.prepare_from_payload(payload)
    result = await reviewer.evaluate_sections(
        prepared.combined_text,
        prepared.document_html,
        expected_titles=prepared.titles,
        expected_numbers=prepared.numbers,
    )

    return FullProcessingResponse(
        overall_score=result.overall_score,
        html=result.html_report,
    )
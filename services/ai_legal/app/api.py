from __future__ import annotations

import json
from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from .llm import client
from .reviews import evaluate_section_file
from .schemas import FullProcessingResponse, HealthResponse
from .sections import build_chunks_from_payload, build_sections_instruction, render_document_html
from .settings import get_settings

router = APIRouter(prefix="/api/sections", tags=["sections"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    models_raw = await client.list_models()
    available = [item.get("name") for item in models_raw.get("models", [])]
    return HealthResponse(
        status="ok",
        model=settings.ollama_model,
        ollama=settings.ollama_base_url,
        model_available=settings.ollama_model in available,
    )


def _validate_document_slicer_payload(payload: dict[str, str]) -> None:
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=422,
            detail=(
                "Тело запроса не похоже на результат document_slicer: "
                "ожидается JSON-объект с ключами part_0..part_16"
            ),
        )

    expected_keys = {f"part_{index}" for index in range(17)}
    missing = sorted(expected_keys - payload.keys())

    if missing:
        missing_readable = ", ".join(missing)
        raise HTTPException(
            status_code=422,
            detail=(
                "Тело запроса не похоже на результат document_slicer: "
                f"отсутствуют ключи {missing_readable}"
            ),
        )


async def _prepare_sections_from_payload(
    payload: dict[str, str]
) -> tuple[str, str | None, list[str], list[int | None], str]:
    _validate_document_slicer_payload(payload)

    sections, specification_text = build_chunks_from_payload(payload)
    combined_text = build_sections_instruction(sections)
    document_html = render_document_html(sections, specification_text)
    titles = [
        "Шапка" if section.number is None and not section.is_specification else (
            "Спецификация" if section.is_specification else f"Раздел {section.number}"
        )
        for section in sections
    ]
    numbers = [section.number for section in sections]
    return combined_text, specification_text, titles, numbers, document_html

@router.post(
    "/full-prepared",
    response_model=FullProcessingResponse,
    response_model_exclude_none=True,
)
async def review_prepared_sections(
    file: UploadFile = File(...),
) -> FullProcessingResponse:
    try:
        raw_payload = (await file.read()).decode("utf-8")
    except UnicodeDecodeError as exc:  # pragma: no cover - defensive decoding
        raise HTTPException(status_code=400, detail="Не удалось прочитать файл как UTF-8") from exc

    if not raw_payload.strip():
        raise HTTPException(status_code=400, detail="Файл с секциями пуст")
    try:
        payload = json.loads(raw_payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Некорректный JSON в файле") from exc

    # CHANGED — используем правильную переменную
    combined_text, specification_text, titles, numbers, document_html = await _prepare_sections_from_payload(payload)

    reviews, overall_score, inaccuracy, red_flags, html_report, debug = await evaluate_section_file(
        combined_text,
        document_html,
        expected_titles=titles,
        expected_numbers=numbers,
    )

    return FullProcessingResponse(
        docx_text=document_html,
        specification_text=specification_text,
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
        sections=reviews,
        html=html_report,
        debug=debug,
        debug_message=None,
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
    combined_text, _, titles, numbers, document_html = await _prepare_sections_from_payload(payload)

    reviews, overall_score, inaccuracy, red_flags, html_report, _ = await evaluate_section_file(
        combined_text,
        document_html,
        expected_titles=titles,
        expected_numbers=numbers,
    )

    return FullProcessingResponse(
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags or "",
        html=html_report,
    )
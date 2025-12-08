from __future__ import annotations

import json
from fastapi import APIRouter, File, HTTPException, UploadFile

from .analysis import PurchaseAnalyzer
from .budget_store import BudgetStore
from .config import get_settings
from .llm_client import LlmClient

router = APIRouter()


@router.post("/analyze")
async def analyze_purchases(spec_file: UploadFile = File(..., description="JSON файл со спецификацией")):
    settings = get_settings()
    budget_store = BudgetStore(settings)
    budget_store.ensure_exists()

    if not spec_file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Файл должен быть в формате JSON")

    analyzer = PurchaseAnalyzer(budget_store, LlmClient(settings))

    try:
        spec_content = await spec_file.read()
        sections_data = json.loads(spec_content)
        spec_data = analyzer.parse_spec(sections_data)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга JSON: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка преобразования спецификации: {exc}") from exc
    except Exception as exc:  # pragma: no cover - unexpected IO errors
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файлов: {exc}") from exc

    return analyzer.analyze(spec_data)


@router.post("/parse-spec")
async def parse_specification(spec_file: UploadFile = File(..., description="Sections.json файл")):
    settings = get_settings()
    analyzer = PurchaseAnalyzer(BudgetStore(settings), LlmClient(settings))

    if not spec_file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Файл должен быть в формате JSON")

    try:
        spec_content = await spec_file.read()
        sections_data = json.loads(spec_content)
        spec_data = analyzer.parse_spec(sections_data)
        return {"status": "success", "spec_data": spec_data}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ошибка преобразования: {exc}") from exc


@router.get("/")
async def root():
    return {
        "message": "Purchase Analysis API is working!",
        "status": "ok",
        "endpoints": {
            "POST /analyze": "Анализ спецификации (требует sections.json и budget.json)",
            "POST /parse-spec": "Только парсинг sections.json",
        },
        "notes": ["Загрузка и выдача budget.json вынесены в сервис budget_service"],
    }

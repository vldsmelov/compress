from __future__ import annotations

import json
from fastapi import APIRouter, Body, HTTPException

from .budget_store import BudgetStore
from .config import get_settings

router = APIRouter()


@router.post("/upload-budget")
async def upload_budget(budget_data: str = Body(..., media_type="text/plain", description="JSON данные")):
    settings = get_settings()
    budget_store = BudgetStore(settings)

    try:
        parsed = json.loads(budget_data)
        valid_items = budget_store.validate_payload(parsed)
        budget_store.save(valid_items)

        categories = [item["КатегорияБюджета"] for item in valid_items]
        total_budget = sum(item["ДоступныйЛимит"] for item in valid_items)
        return {
            "status": "success",
            "message": "Бюджет успешно загружен из 1С",
            "details": {
                "file_path": str(budget_store.path.absolute()),
                "categories_count": len(valid_items),
                "total_budget": total_budget,
                "categories": categories,
            },
        }
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Невалидный JSON: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Некорректные данные: {exc}") from exc
    except Exception as exc:  # pragma: no cover - unexpected IO errors
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {exc}") from exc


@router.get("/get-budget")
async def get_budget():
    settings = get_settings()
    budget_store = BudgetStore(settings)

    try:
        budget_data = budget_store.load()
        if not budget_data:
            return {
                "status": "not_found",
                "message": "Файл budget.json не найден. Загрузите его через /upload-budget",
                "budget_data": [],
            }

        return {"status": "success", "budget_data": budget_data}
    except Exception as exc:  # pragma: no cover - unexpected IO errors
        raise HTTPException(status_code=500, detail=f"Ошибка при чтении файла: {exc}") from exc


@router.get("/")
async def root():
    return {
        "message": "Budget service is working!",
        "status": "ok",
        "endpoints": {
            "POST /upload-budget": "Загрузить бюджет из 1С (text/plain)",
            "GET /get-budget": "Получить текущий budget.json",
        },
    }

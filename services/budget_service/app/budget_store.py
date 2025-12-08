from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

from .config import Settings


class BudgetStore:
    """Filesystem-backed repository for budget.json with validation helpers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self.settings.budget_path

    def load(self) -> List[Dict[str, Any]]:
        """Read budget.json contents or return an empty list if absent."""
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, budget_items: List[Dict[str, Any]]) -> None:
        """Persist validated budget items to disk."""
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(budget_items, file, ensure_ascii=False, indent=2)

    def validate_payload(self, payload: Any) -> List[Dict[str, Any]]:
        """Ensure uploaded budget data is a list of objects with required fields."""
        if not isinstance(payload, list):
            raise ValueError("Данные бюджета должны быть массивом (списком)")

        valid_items: List[Dict[str, Any]] = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise ValueError(f"Элемент {index} должен быть объектом (словарем)")

            if "КатегорияБюджета" not in item:
                raise ValueError(f"Элемент {index} не содержит поле 'КатегорияБюджета'")
            if "ДоступныйЛимит" not in item:
                raise ValueError(f"Элемент {index} не содержит поле 'ДоступныйЛимит'")

            valid_item: Dict[str, Any] = {
                "КатегорияБюджета": str(item["КатегорияБюджета"]).strip(),
                "ДоступныйЛимит": float(item["ДоступныйЛимит"]),
            }
            for key, value in item.items():
                if key not in valid_item:
                    valid_item[key] = value
            valid_items.append(valid_item)

        return valid_items

    def ensure_exists(self) -> None:
        """Raise a user-facing HTTP error if budget.json is missing."""
        if not self.path.exists():
            raise HTTPException(
                status_code=400,
                detail="Файл budget.json не найден. Загрузите его через /upload-budget",
            )

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from .budget_store import BudgetStore
from .llm_client import LlmClient
from .spec_parser import parse_spec_from_sections


class PurchaseAnalyzer:
    """Run LLM-based categorization and budget comparison for purchase specs."""

    def __init__(self, budget_store: BudgetStore, llm_client: LlmClient) -> None:
        self.budget_store = budget_store
        self.llm_client = llm_client

    def parse_spec(self, sections_data: dict) -> dict:
        """Convert raw sections.json content into a structured spec dictionary."""
        return parse_spec_from_sections(sections_data)

    def analyze(self, spec_data: dict) -> Dict[str, Any]:
        """Validate spec structure, categorize items, and compute budget sufficiency."""
        budget_data = self.budget_store.load()
        if not budget_data:
            raise HTTPException(
                status_code=400,
                detail="Файл budget.json не найден. Загрузите его через /upload-budget",
            )

        if not isinstance(spec_data, dict) or "items" not in spec_data:
            raise HTTPException(status_code=400, detail="Spec файл должен содержать объект с полем 'items'")
        if not isinstance(spec_data.get("items"), list):
            raise HTTPException(status_code=400, detail="Поле 'items' в spec файле должно быть массивом")

        for item in spec_data["items"]:
            if not all(key in item for key in ["name", "qty", "unit", "price", "amount"]):
                raise HTTPException(
                    status_code=400,
                    detail="Каждый товар должен содержать поля: name, qty, unit, price, amount",
                )

        budget_dict: Dict[str, float] = {item["КатегорияБюджета"]: item["ДоступныйЛимит"] for item in budget_data}
        available_categories = list(budget_dict.keys())

        item_names = [item["name"] for item in spec_data["items"]]
        categories_for_items = self.llm_client.categorize_items(item_names, available_categories)

        categorized_items_by_category: Dict[str, List[dict]] = {}
        for index, item in enumerate(spec_data["items"]):
            category = categories_for_items[index] if index < len(categories_for_items) else "Неопределенная категория"
            item_with_category = {
                "name": item["name"],
                "qty": item["qty"],
                "unit": item["unit"],
                "price": item["price"],
                "amount": item["amount"],
                "country": item.get("country", "Не указано"),
                "category": category,
            }

            categorized_items_by_category.setdefault(category, []).append(
                {
                    "название": item_with_category["name"],
                    "количество": item_with_category["qty"],
                    "единица_измерения": item_with_category["unit"],
                    "цена_за_единицу": item_with_category["price"],
                    "сумма_покупки": item_with_category["amount"],
                    "страна": item_with_category["country"],
                    "категория": item_with_category["category"],
                }
            )

        categories_output = []
        for category, items in categorized_items_by_category.items():
            total_amount = sum(item["сумма_покупки"] for item in items)
            available_budget = budget_dict.get(category, 0.0)
            needed_amount = max(0.0, total_amount - available_budget)
            enough = available_budget >= total_amount

            categories_output.append(
                {
                    "категория": category,
                    "товары": items,
                    "доступный_бюджет_категории": available_budget,
                    "общая_сумма_товаров": total_amount,
                    "необходимая_сумма": needed_amount,
                    "хватает": enough,
                }
            )

        return {
            "categories": categories_output,
            "total_spec_amount": spec_data.get("total"),
            "items_count": len(spec_data.get("items", [])),
            "budget_source": str(self.budget_store.path.relative_to(self.budget_store.settings.data_dir.parent)),
        }

from __future__ import annotations

"""Lightweight synchronous wrapper for categorizing items via Ollama."""

import json
from typing import Iterable, List

import requests

from .config import Settings


class LlmClient:
    """Send a simple single-message prompt to categorize spec items by budget category."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def categorize_items(self, item_names: Iterable[str], available_categories: List[str]) -> List[str]:
        """Ask the LLM to map each item name to one of the allowed categories in order."""
        names = list(item_names)
        if not names:
            return []

        default_category = "Неопределенная категория"
        categories_result = [default_category] * len(names)
        categories_str = ", ".join(available_categories)
        items_block = "\n".join(f"{idx + 1}. {name}" for idx, name in enumerate(names))

        prompt = f"""
    Ты должен отнести каждый товар к одной из категорий бюджета.

    Доступные категории:
    {categories_str}

    Список товаров (важен порядок):
    {items_block}

    Верни СТРОГО корректный JSON-массив строк без комментариев и лишнего текста, например:
    ["Категория1", "Категория2", "Неопределенная категория", ...]

    Количество элементов в массиве ДОЛЖНО строго совпадать с количеством товаров,
    а порядок должен соответствовать списку товаров выше.
    Каждый элемент массива — это ИМЯ категории из доступных категорий
    или строка "{default_category}", если подходящей категории нет.
    """

        options: dict[str, object] = {
            "temperature": self.settings.ollama_temperature,
            "num_predict": self.settings.ollama_max_tokens,
        }
        if self.settings.ollama_num_ctx:
            options["num_ctx"] = self.settings.ollama_num_ctx

        payload = {
            "model": self.settings.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": options,
        }

        try:
            response = requests.post(
                self.settings.ollama_url,
                json=payload,
                timeout=self.settings.ollama_timeout,
            )
            if response.status_code != 200:
                return categories_result

            result = response.json()
            content = result.get("message", {}).get("content", "")
            start = content.find("[")
            end = content.rfind("]")
            if start == -1 or end == -1 or end <= start:
                return categories_result

            json_str = content[start : end + 1].strip()
            parsed = json.loads(json_str)
            if not isinstance(parsed, list):
                return categories_result

            cleaned: List[str] = []
            for cat in parsed:
                if not isinstance(cat, str):
                    cleaned.append(default_category)
                    continue

                cat_clean = (
                    cat.replace(".", "")
                    .replace('"', "")
                    .replace("'", "")
                    .strip()
                )
                cleaned.append(cat_clean if cat_clean in available_categories else default_category)

            if len(cleaned) < len(names):
                cleaned.extend([default_category] * (len(names) - len(cleaned)))
            elif len(cleaned) > len(names):
                cleaned = cleaned[: len(names)]

            return cleaned
        except Exception:
            return categories_result

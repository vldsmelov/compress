from __future__ import annotations

"""Helpers to parse commodity specification tables from sections.json content."""

import re
from typing import Dict, List


def clean_number_string(number_str: str) -> float:
    """Normalize messy numeric strings (spaces, commas, currency symbols) into a float."""
    if not number_str or number_str.strip() == "":
        return 0.0

    cleaned = number_str.replace("\xa0", "").replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^\d.-]", "", cleaned)

    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def parse_spec_from_sections(sections_data: dict) -> dict:
    """Extract a structured spec (items and totals) from section text exported by document_slicer."""
    try:
        table_part = None
        for key, value in sections_data.items():
            if "TABLE:" in value and "Наименование и характеристика Товара" in value:
                table_part = value
                break

        if not table_part:
            raise ValueError("Не найдена таблица с товарами в sections.json")

        lines = table_part.split("\n")
        items: List[Dict[str, object]] = []
        total_amount = 0.0

        for line in lines:
            if "TABLE:" in line and "|" in line:
                clean_line = line.replace("TABLE:", "").strip()
                columns = [col.strip() for col in clean_line.split("|")]

                if (
                    len(columns) >= 6
                    and "Наименование" not in columns[1]
                    and "ИТОГО" not in columns[1]
                    and "В том числе НДС" not in columns[1]
                    and columns[1]
                    and not columns[1].isdigit()
                ):
                    try:
                        name = columns[1]
                        qty = clean_number_string(columns[2])
                        unit = columns[3]
                        price = clean_number_string(columns[4])
                        amount = clean_number_string(columns[5])
                        country = columns[6] if len(columns) > 6 else "Не указано"

                        item = {
                            "name": name,
                            "qty": int(qty) if qty.is_integer() else qty,
                            "unit": unit,
                            "price": price,
                            "amount": amount,
                            "country": country,
                        }

                        items.append(item)
                        total_amount += amount

                    except (ValueError, IndexError):
                        continue

        return {
            "items": items,
            "total": total_amount,
            "vat": 20,
            "warning": None,
        }

    except Exception as exc:
        raise ValueError(f"Ошибка парсинга спецификации: {exc}")

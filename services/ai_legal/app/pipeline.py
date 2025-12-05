from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException

from .sections import build_chunks_from_payload, build_sections_instruction, render_document_html


@dataclass(slots=True)
class SectionPreparation:
    """Normalized bundle of text, metadata, and HTML ready for review."""
    combined_text: str
    specification_text: str | None
    titles: list[str]
    numbers: list[int | None]
    document_html: str


class SectionPipeline:
    """Validates document_slicer payloads and prepares combined prompts."""

    def __init__(self, *, expected_parts: int = 17) -> None:
        self.expected_keys = {f"part_{index}" for index in range(expected_parts)}

    def _validate_payload(self, payload: dict[str, str]) -> None:
        """Ensure the request body matches document_slicer output shape."""
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Тело запроса не похоже на результат document_slicer: "
                    "ожидается JSON-объект с ключами part_0..part_16"
                ),
            )

        missing = sorted(self.expected_keys - payload.keys())
        if missing:
            missing_readable = ", ".join(missing)
            raise HTTPException(
                status_code=422,
                detail=(
                    "Тело запроса не похоже на результат document_slicer: "
                    f"отсутствуют ключи {missing_readable}"
                ),
            )

    def prepare_from_payload(self, payload: dict[str, str]) -> SectionPreparation:
        """Build concatenated content, section titles, and HTML from a raw JSON payload."""
        self._validate_payload(payload)

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
        return SectionPreparation(
            combined_text=combined_text,
            specification_text=specification_text,
            titles=titles,
            numbers=numbers,
            document_html=document_html,
        )

    def prepare_from_text(self, payload: str) -> SectionPreparation:
        """Same as :meth:`prepare_from_payload` but accepts raw JSON string from UploadFile."""
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Некорректный JSON в файле") from exc
        if not decoded:
            raise HTTPException(status_code=400, detail="Файл с секциями пуст")
        return self.prepare_from_payload(decoded)


pipeline = SectionPipeline()

__all__ = ["SectionPreparation", "SectionPipeline", "pipeline"]

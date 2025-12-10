from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import HTTPException

INSTRUCTIONS_DIR = Path(__file__).resolve().parent / "instructions"


@dataclass(slots=True)
class SectionChunk:
    number: int | None
    title: str
    content: str
    is_specification: bool = False


def _extract_part_index(key: str) -> int | None:
    match = re.search(r"(\d+)", key)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _normalize_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return fallback


def _looks_like_specification(key: str, index: int | None) -> bool:
    lowered = key.lower()
    if "spec" in lowered or "спец" in lowered or "специф" in lowered:
        return True
    if index is not None and index >= 16:
        return True
    return False


def build_chunks_from_payload(payload: str | dict[str, str]) -> tuple[list[SectionChunk], str | None]:
    if isinstance(payload, dict):
        raw_payload = json.dumps(payload, ensure_ascii=False)
    else:
        raw_payload = payload
    try:
        data = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Тело запроса должно содержать корректный JSON") from exc

    if not isinstance(data, dict) or not data:
        raise HTTPException(status_code=422, detail="Тело запроса с секциями пусто или имеет неверный формат")

    entries: list[tuple[str, int | None, str]] = []
    for key, value in data.items():
        if not isinstance(value, str):
            continue
        content = value.strip()
        if not content:
            continue
        entries.append((key, _extract_part_index(key), content))

    if not entries:
        raise HTTPException(status_code=422, detail="Не удалось найти текстовые секции в файле")

    entries.sort(key=lambda item: (item[1] if item[1] is not None else float("inf"), item[0]))

    sections: list[SectionChunk] = []
    specification_text: str | None = None

    for _, (key, index, content) in enumerate(entries):
        
        is_specification = _looks_like_specification(key, index)
        if is_specification:
            specification_text = specification_text or content

        number = None if index is None or index == 0 else index
        fallback_title = (
            "Шапка"
            if number is None
            else ("Спецификация" if is_specification else f"Раздел {number}")
        )
        title = _normalize_title(content, fallback_title)
        sections.append(
            SectionChunk(
                number=number,
                title=title,
                content=content,
                is_specification=is_specification,
            )
        )

    if not sections:
        raise HTTPException(status_code=422, detail="Секции не содержат текстового контента")

    return sections, specification_text


def _load_instruction_text(number: int | None) -> str | None:
    index = number or 0
    path = INSTRUCTIONS_DIR / f"{index}.txt"
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return None


def build_sections_instruction(sections: list[SectionChunk]) -> str:
    parts: list[str] = []
    for section in sections:
        is_header = section.number is None
        instruction_index = 16 if section.is_specification else section.number
        section_label = (
            "Шапка"
            if is_header and not section.is_specification
            else "Спецификация" if section.is_specification else f"Раздел {section.number}"
        )
        instruction_text = _load_instruction_text(instruction_index)
        if instruction_text:
            parts.append(instruction_text)
        parts.append(f"{section_label}:")
        parts.append(section.content or "(раздел пуст)")
        parts.append("")


    return "\n".join(parts).rstrip()


def render_document_html(sections: Iterable[SectionChunk], specification_text: str | None) -> str:
    blocks: list[str] = []

    for section in sections:
        heading = "Шапка" if section.number is None and not section.is_specification else (
            "Спецификация" if section.is_specification else f"Раздел {section.number}"
        )
        blocks.append(
            f"""
            <section>
                <h2>{html.escape(heading)}: {html.escape(section.title)}</h2>
                <pre>{html.escape(section.content)}</pre>
            </section>
            """.strip()
        )

    has_spec_section = any(section.is_specification for section in sections)

    if specification_text and not has_spec_section:
        blocks.append(
            f"""
            <section>
                <h2>Приложение №1 Спецификация</h2>
                <pre>{html.escape(specification_text)}</pre>
            </section>
            """.strip()
        )

    return "\n".join(blocks)
from __future__ import annotations

import html
import json
import math
import re
import textwrap
from typing import Iterable

import httpx

from .llm import build_debug_info, client, extract_reply
from .schemas import LlmDebugInfo, SectionReview

_SYSTEM_PROMPT = (
    "Ты юрист. Проанализируй шапку, каждый раздел документа и спецификацию после строки 'Инструкция'. "
    "Верни JSON с ключом sections (массив объектов со свойствами title, resume, risks, score, "
    "где score — целое число от 1 до 10) и опциональными ключами INACCURACY (строка или массив), "
    "который содержит перечень ключевых несоответствий по всему документу. RED_FLAGS (строка или массив),"
    "который выводит только ошибку по общей сумме, если она разная на протяжении документа, и ошибку по Сторонам (Покупатель и Поставщик)"
    "если они разные на протяжении документа, в противном случае оставь данный пункт пустым."
    "Внимание: RED_FLAGS заполнять только если есть ошибки! Если ошибок нет, оставить пустым. Если есть любые другие замечания, кроме суммы и сторон - игнорируй их."
    "Возвращай только json, без дополнительных обозначений типа ```json```"
    "Анализируй текст, таблицы и структурированные блоки одинаково."
    "Если раздел представлен таблицей — всё равно верни JSON с resume, risks, score."
    "Сейчас декабрь 2025 года."
)


def _build_alignment_instruction(titles: list[str]) -> str:
    ordered_titles = ", ".join(titles)
    sections_count = len(titles)
    return (
        "Ты должен вернуть разделы в том же порядке, что и во входных данных. "
        f"Всего разделов (включая шапку и спецификацию) — {sections_count}. "
        f"Порядок разделов: {ordered_titles}. "
        "Ответ json должен содержать ключ sections с массивом ровно из этого количества элементов. "
        "Если по разделу нет информации, всё равно заполни его: resume — 'Информации недостаточно',"
        " risks — 'Риски не выявлены', score — '5'. "
        "Резюме и риски должны быть максимально лаконичными (не более 2 предложений на поле)."
    )


def _parse_titles(source: str) -> list[str]:
    pattern = re.compile(r"^(Шапка|Раздел\s+\d+|Спецификация):", re.MULTILINE)
    titles: list[str] = []
    for match in pattern.finditer(source):
        titles.append(match.group(1))
    return titles

def _extract_section_number_from_title(title: str) -> int | None:
    match = re.search(r"(\d+)", title)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None

def _coerce_to_list(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _extract_items_from_parsed(parsed: object) -> list[dict]:
    if isinstance(parsed, dict):
        if "sections" in parsed and isinstance(parsed["sections"], list):
            return _coerce_to_list(parsed["sections"])
        if "items" in parsed and isinstance(parsed["items"], list):
            return _coerce_to_list(parsed["items"])
        if "reviews" in parsed and isinstance(parsed["reviews"], list):
            return _coerce_to_list(parsed["reviews"])
        return _coerce_to_list(parsed)
    return _coerce_to_list(parsed)


def _coerce_red_flags(parsed: object) -> str | None:
    if isinstance(parsed, dict):
        for key in ("red_flags", "RED_FLAGS"):
            if key in parsed and parsed[key]:
                value = parsed[key]
                if isinstance(value, list):
                    return "; ".join(str(item) for item in value if str(item).strip()).strip() or None
                return str(value).strip() or None
    return None


def _coerce_inaccuracy(parsed: object) -> str | None:
    if isinstance(parsed, dict):
        for key in ("inaccuracy", "INACCURACY"):
            if key in parsed and parsed[key]:
                value = parsed[key]
                if isinstance(value, list):
                    return "; ".join(str(item) for item in value if str(item).strip()).strip() or None
                return str(value).strip() or None
    return None


def _looks_like_section(item: dict) -> bool:
    return any(key in item for key in ("title", "resume", "risks", "score"))


def _extract_response_payload(text: str) -> tuple[list[dict], str | None, str | None]:
    try:
        parsed = json.loads(text)
        inaccuracy = _coerce_inaccuracy(parsed)
        red_flags = _coerce_red_flags(parsed)
        items = _extract_items_from_parsed(parsed)
        filtered = [item for item in items if _looks_like_section(item)]
        if filtered:
            return filtered, inaccuracy, red_flags
    except json.JSONDecodeError:
        pass

    matches = re.findall(r"\{[^{}]*\}", text, flags=re.DOTALL)
    items: list[dict] = []
    inaccuracy: str | None = None
    red_flags: str | None = None
    for chunk in matches:
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            possible_inaccuracy = _coerce_inaccuracy(parsed)
            inaccuracy = inaccuracy or possible_inaccuracy
            possible_flags = _coerce_red_flags(parsed)
            red_flags = red_flags or possible_flags
            if _looks_like_section(parsed):
                items.append(parsed)
    return items, inaccuracy, red_flags


def _normalize_reviews(
    raw_items: Iterable[dict],
    titles: list[str],
    numbers: list[int | None] | None = None,
) -> list[SectionReview]:
    normalized: list[SectionReview] = []
    padded_items = list(raw_items)
    if titles and len(padded_items) < len(titles):
        padded_items.extend({} for _ in range(len(titles) - len(padded_items)))

    for index, item in enumerate(padded_items):
        fallback_title = titles[index] if index < len(titles) else f"Раздел {index + 1}"
        title = str(item.get("title") or fallback_title)
        resume_raw = str(item.get("resume") or "").strip()
        risks_raw = str(item.get("risks") or "").strip()
        score_raw = str(item.get("score") or "").strip()
        resume = resume_raw or "Информации недостаточно"
        risks = risks_raw or "Риски не выявлены"
        score = score_raw or "5"
        number = None
        if numbers and index < len(numbers):
            number = numbers[index]
        if number is None:
            number = _extract_section_number_from_title(title)
        normalized.append(
            SectionReview(
                number=number,
                title=title or f"Раздел {index + 1}",
                resume=resume,
                risks=risks,
                score=score,
            )
        )
    return normalized


def _extract_numeric_score(score: str) -> float | None:
    match = re.search(r"([0-9]+(?:[\.,][0-9]+)?)", score)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _calculate_average_score(reviews: list[SectionReview]) -> float | None:
    values = [value for review in reviews if (value := _extract_numeric_score(review.score)) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _score_to_color(score: float | None) -> str:
    if score is None or math.isnan(score):
        return "#e5e7eb"
    clamped = max(1.0, min(10.0, score))
    hue = 0 + (120 * (clamped - 1) / 9)
    return f"hsl({hue:.0f}, 75%, 45%)"

def _score_to_percent(score: float | None) -> float:
    if score is None or math.isnan(score):
        return 0.0
    clamped = max(1.0, min(10.0, score))
    return round((clamped / 10) * 100, 2)

def _build_html_report(
    reviews: list[SectionReview],
    overall_score: float | None,
    inaccuracy: str | None,
    red_flags: str | None,
    document_html: str | None = None,
) -> str:
    cards = []
    for index, review in enumerate(reviews, start=1):
        score_numeric = _extract_numeric_score(review.score)
        bar_width = _score_to_percent(score_numeric)
        bar_color = _score_to_color(score_numeric)
        display_score = (
            f"{score_numeric:.1f}".rstrip("0").rstrip(".")
            if score_numeric is not None
            else (review.score or "-")
        )
        section_prefix = f"{review.number}. " if review.number is not None else ""
        card = f"""
        <section class="section-card">
            <div class="section-card__header">
                <h2>{html.escape(section_prefix + review.title)}</h2>
                <div class="score-badge" style="border-color:{bar_color}; color:{bar_color};">Оценка: {html.escape(display_score)} / 10</div>
            </div>
            <div class="progress">
                <div class="progress__track">
                    <div class="progress__fill" style="width:{bar_width}%; background:{bar_color};"></div>
                </div>
                <span class="progress__value">{html.escape(display_score)}</span>
            </div>
            <div class="section-card__block">
                <h3>Резюме</h3>
                <p>{html.escape(review.resume) or "(пусто)"}</p>
            </div>
            <div class="section-card__block">
                <h3>Риски</h3>
                <p>{html.escape(review.risks) or "(пусто)"}</p>
            </div>
        </section>
        """.strip()
        cards.append(card)

    overall_color = _score_to_color(overall_score)
    overall_percent = _score_to_percent(overall_score)
    overall_label = (
        f"{overall_score:.2f}".rstrip("0").rstrip(".") if overall_score is not None else "-"
    )
    red_flags_content = html.escape(red_flags) if red_flags else "Критических ошибок не обнаружено"
    inaccuracy_content = html.escape(inaccuracy) if inaccuracy else "Ключевые неточности не выявлены"

    document_block = (
        f"""
        <details class="report__accordion">
            <summary>Показать полный текст договора</summary>
            <div class="report__document">{document_html}</div>
        </details>
        """.strip()
        if document_html
        else ""
    )

    return f"""
    <html>
    <head>
        <style>
            :root {{
                color-scheme: light;
                font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            }}
            body {{ margin: 0; padding: 18px; background: #f3f4f6; color: #0f172a; }}
            .report {{ max-width: 960px; margin: 0 auto; display: grid; gap: 14px; }}
            .report__summary {{ background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06); border: 1px solid #e2e8f0; display: grid; gap: 10px; }}
            .report__summary-row {{ display: grid; gap: 8px; }}
            .progress {{ display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 12px; }}
            .progress__track {{ width: 100%; height: 12px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }}
            .progress__fill {{ height: 100%; border-radius: 999px; transition: width 0.2s ease; box-shadow: inset 0 0 6px rgba(0,0,0,0.08); }}
            .progress__value {{ font-weight: 700; color: #0f172a; }}
            .report__block {{ border-radius: 12px; padding: 14px; background: #fff; border: 1px solid #e2e8f0; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04); }}
            .report__block--danger {{ background: #fef2f2; border-color: #fecaca; color: #991b1b; }}
            .report__block--warning {{ background: #fff7ed; border-color: #fed7aa; color: #9a3412; }}
            .report__block-title {{ margin: 0 0 8px; font-size: 16px; font-weight: 700; }}
            .section-card {{ background: #fff; border-radius: 12px; padding: 14px; border: 1px solid #e2e8f0; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04); display: grid; gap: 10px; }}
            .section-card__header {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
            .section-card__header h2 {{ margin: 0; font-size: 18px; }}
            .section-card__block h3 {{ margin: 0 0 4px; font-size: 15px; }}
            .section-card__block p {{ margin: 0; line-height: 1.5; }}
            .score-badge {{ border: 1px solid transparent; padding: 6px 10px; border-radius: 10px; font-weight: 700; background: #f8fafc; }}
            .report__sections {{ display: grid; gap: 12px; }}
            .report__accordion {{ border: 1px solid #e2e8f0; background: #fff; border-radius: 12px; padding: 12px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04); }}
            .report__accordion summary {{ cursor: pointer; font-weight: 700; color: #0f172a; }}
            .report__document {{ margin-top: 10px; max-height: 360px; overflow: auto; background: #f8fafc; border-radius: 10px; padding: 12px; border: 1px solid #e2e8f0; }}
            pre {{ white-space: pre-wrap; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace; }}
        </style>
    </head>
    <body>
        <div class="report">
            <div class="report__summary">
                <div class="report__summary-row">
                    <div class="progress">
                        <div class="progress__track">
                            <div class="progress__fill" style="width:{overall_percent}%; background:{overall_color};"></div>
                        </div>
                        <span class="progress__value">{overall_label if overall_label else "-"}</span>
                    </div>
                    <div class="score-badge" style="border-color:{overall_color}; color:{overall_color};">Общая оценка документа</div>
                </div>
            </div>
            {document_block}
            <div class="report__block report__block--danger">
                <div class="report__block-title">RED FLAGS</div>
                <p>{red_flags_content}</p>
            </div>
            <div class="report__block report__block--warning">
                <div class="report__block-title">Неточности</div>
                <p>{inaccuracy_content}</p>
            </div>
            <div class="report__sections">{''.join(cards)}</div>
        </div>
    </body>
    </html>
    """.strip()


async def evaluate_section_file(
    content: str,
    document_html: str | None = None,
    *,
    role_key: str = "lawyer",
    expected_titles: list[str] | None = None,
    expected_numbers: list[int | None] | None = None,
) -> tuple[list[SectionReview], float | None, str | None, str | None, str, LlmDebugInfo | None]:
    titles = expected_titles or _parse_titles(content)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "system", "content": _build_alignment_instruction(titles)},
        {"role": "user", "content": content},
    ]

    try:
        raw = await client.chat(messages)
    except httpx.HTTPStatusError as exc:
        raise
    debug = build_debug_info(messages, raw)
    reply = extract_reply(raw)
    raw_items, inaccuracy, red_flags = _extract_response_payload(reply)
    if not raw_items and titles:
        raw_items = [{} for _ in titles]
    reviews = _normalize_reviews(raw_items, titles, expected_numbers)
    average_score = _calculate_average_score(reviews)
    html_report = _build_html_report(
        reviews,
        average_score,
        inaccuracy,
        red_flags,
        document_html,
    )
    return reviews, average_score, inaccuracy, red_flags, html_report, debug


__all__ = ["evaluate_section_file"]
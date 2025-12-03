from fastapi import UploadFile
import json
import re
from io import BytesIO

from docx import Document
from docx.document import Document as _Document
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph


def _is_docx(file: UploadFile) -> bool:
    return (
        (file.filename or "").lower().endswith(".docx")
        or file.content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def _is_heading_paragraph(paragraph, text: str) -> bool:
    style_name = (paragraph.style.name if paragraph.style else "").lower()

    if "heading" in style_name or "\u0437\u0430\u0433\u043e\u043b\u043e\u0432\u043e\u043a" in style_name:
        return True

    if text == "СПЕЦИФИКАЦИЯ":
        return True

    return bool(
        re.match(r"^\d{1,3}\.\s(?!\d).+$", text)
    )


def _iter_block_items(parent):
    if isinstance(parent, _Document):
        parent_element = parent.element.body
    elif isinstance(parent, _Cell):
        parent_element = parent._tc
    else:  # pragma: no cover - defensive safeguard
        raise ValueError("Unsupported parent type for block iteration")

    for child in parent_element.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield Table(child, parent)


def _extract_sections_from_docx(content: bytes) -> list[str]:
    document = Document(BytesIO(content))

    sections: list[list[str]] = [[]]  # first section is the document header
    spec_section_started = False
    stop_processing = False

    for block in _iter_block_items(document):
        if stop_processing:
            break

        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue

            is_heading = _is_heading_paragraph(block, text)

            if is_heading:
                if text == "СПЕЦИФИКАЦИЯ":
                    spec_section_started = True

                if sections[-1]:
                    sections.append([])
                elif len(sections) == 1 and not sections[-1]:
                    # keep the empty header, start a new section for the first heading
                    sections.append([])

            sections[-1].append(text)

            if spec_section_started and "общая сумма договора" in text.lower():
                stop_processing = True
        elif isinstance(block, Table):
            for row in block.rows:
                if stop_processing:
                    break
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if not cell_text:
                        continue

                    sections[-1].append(cell_text)

                    if spec_section_started and "общая сумма договора" in cell_text.lower():
                        stop_processing = True
                        break

    return ["\n".join(chunk) for chunk in sections]


def _extract_text_from_docx(content: bytes) -> str:
    sections = _extract_sections_from_docx(content)
    non_empty_sections = [section for section in sections if section.strip()]
    return "\n\n".join(non_empty_sections) if non_empty_sections else "\n\n".join(sections)


async def read_text_and_sections_from_upload(
    file: UploadFile,
) -> tuple[str, list[str] | None]:
    content = await file.read()

    if _is_docx(file):
        try:
            sections = _extract_sections_from_docx(content)
            text = _extract_text_from_docx(content)
            return text, sections
        except Exception:
            # Fallback to decoding as plain text if DOCX parsing fails
            pass

    try:
        text = content.decode("utf-8")
    except Exception:
        text = content.decode("cp1251", errors="ignore")

    return text, None


async def read_text_from_upload(file: UploadFile) -> str:
    text, _ = await read_text_and_sections_from_upload(file)
    return text


async def read_json_from_upload(file: UploadFile):
    text = await read_text_from_upload(file)
    return json.loads(text)

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import HTTPException, UploadFile

from .clients import AiEconomClient, AiLegalClient, ContractExtractorClient, ServiceResult
from .config import Settings
from .document.reader import load_blocks
from .document.spec_extractor import extract_specification_from_blocks
from .services.section_splitter import SectionChunk, split_into_sections


class SectionSerializer:
    """Helper that converts parsed sections into the JSON shape expected by downstream services."""
    @staticmethod
    def _section_to_text(section: SectionChunk) -> str:
        """Join a section title and its body into a normalized text snippet."""
        parts = [section.title.strip()] if section.title else []
        if section.content:
            parts.append(section.content.strip())
        return "\n".join(part for part in parts if part)

    @classmethod
    def serialize(cls, sections: list[SectionChunk], blocks_html: str) -> dict[str, str]:
        """Render sections and fallback HTML/specification text into part_0..part_16 keys."""
        payload: dict[str, str] = {f"part_{index}": "" for index in range(17)}

        for section in sections:
            if section.number is None:
                key = "part_0"
            elif 1 <= section.number <= 15:
                key = f"part_{section.number}"
            else:
                continue

            section_text = cls._section_to_text(section)
            if not section_text:
                continue

            existing = payload.get(key, "")
            payload[key] = "\n\n".join(
                value for value in (existing.strip(), section_text) if value
            )

        payload["part_16"] = blocks_html.strip()
        return payload


class SpecificationExtractor:
    """Thin wrapper that extracts table rows from the parsed document blocks."""
    @staticmethod
    def extract(blocks: list[Any]) -> str:
        """Convert detected tables into a plain-text representation for part_16."""
        try:
            spec_result = extract_specification_from_blocks(blocks)
            lines = []
            for table_region in spec_result.tables:
                for row in table_region.block.rows or []:
                    row_text = " | ".join(cell.strip() for cell in row)
                    lines.append(f"TABLE: {row_text}")

            return "\n".join(lines)
        except Exception:
            return ""


class DocumentPipeline:
    """High-level pipeline that reads uploads, slices sections, and dispatches them to services."""
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ai_econom_client = AiEconomClient(settings)
        self.ai_legal_client = AiLegalClient(settings)
        self.contract_extractor_client = ContractExtractorClient(settings)

    async def read_upload(self, file: UploadFile) -> tuple[str, bytes]:
        """Read an uploaded file into memory and validate that it is non-empty."""
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл пуст или не содержит данных")
        filename = file.filename or "document.docx"
        return filename, content

    def extract_parts(self, file_name: str, content: bytes) -> dict[str, str]:
        """Slice a DOCX payload into numbered sections plus a specification block."""
        try:
            blocks = load_blocks(file_name, content)
        except Exception as exc:  # pragma: no cover - defensive parsing guard
            raise HTTPException(status_code=400, detail=f"Не удалось разобрать файл: {exc}") from exc

        sections = split_into_sections(blocks)
        specification_text = SpecificationExtractor.extract(blocks)
        return SectionSerializer.serialize(sections, specification_text)

    def persist_sections(self, parts: dict[str, str]) -> dict[str, Path]:
        """Persist generated parts to disk for observability and reuse."""
        self.settings.ensure_data_dir()

        sections_path = self.settings.sections_path
        part_16_path = self.settings.part_16_path

        try:
            sections_path.write_text(
                json.dumps(parts, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            part_16_payload = {"part_16": parts.get("part_16", "")}
            part_16_path.write_text(
                json.dumps(part_16_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Best-effort persistence; errors are not fatal for request
            pass

        return {"sections": sections_path, "part_16": part_16_path}

    def _select_contract_sections(self, parts: dict[str, str]) -> dict[str, str]:
        """Select only the section subset required by contract_extractor."""
        selected = {
            key: parts.get(key, "").strip() for key in self.settings.contract_extractor_sections
        }
        return {key: value for key, value in selected.items() if value}

    @staticmethod
    def _collect_responses(service_results: list[ServiceResult]) -> dict[str, Any]:
        """Merge responses from async service calls into a single payload."""
        responses: dict[str, Any] = {
            "ai_econom": None,
            "ai_legal": None,
            "sb_ai": None,
            "contract_extractor": None,
        }

        for result in service_results:
            payload = result.payload
            if result.service == "contract_extractor":
                contract_payload = payload
                sb_payload = payload
                if isinstance(payload, dict):
                    contract_payload = payload.get("result", payload)
                    sb_payload = payload.get("sb_ai", payload)

                responses["contract_extractor"] = contract_payload
                responses["sb_ai"] = sb_payload
            else:
                responses[result.service] = payload

        for key in responses:
            if responses[key] is None:
                responses[key] = {}

        return responses

    async def dispatch(self, parts: Dict[str, str], sections_path: Path) -> Dict[str, Any]:
        """Send prepared sections to all downstream services in parallel."""
        contract_sections = self._select_contract_sections(parts)
        if not contract_sections:
            return {
                "ai_econom": {},
                "ai_legal": {},
                "sb_ai": {},
                "contract_extractor": {
                    "error": "No contract sections available for extraction",
                },
            }

        payload = {"sections": contract_sections}

        async with httpx.AsyncClient(timeout=self.settings.http_timeout, trust_env=False) as client:
            ai_econom_task = asyncio.create_task(
                self.ai_econom_client.analyze(client, sections_path)
            )
            ai_legal_task = asyncio.create_task(
                self.ai_legal_client.analyze(client, sections_path)
            )
            contract_extractor_task = asyncio.create_task(
                self.contract_extractor_client.extract(client, payload)
            )
            service_results = await asyncio.gather(
                ai_econom_task, ai_legal_task, contract_extractor_task
            )

        return self._collect_responses(service_results)

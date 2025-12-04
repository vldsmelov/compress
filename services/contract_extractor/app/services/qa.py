"""Utility for asking targeted questions about specific document sections."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

from ..core.config import CONFIG
from .normalize import normalize_whitespace
from .ollama_client import OllamaClient


class SectionQuestionAnswering:
    """Lightweight helper that asks the LLM about selected document sections.

    The class builds a compact prompt that contains only the requested parts of
    the document, a natural language question, and a JSON skeleton with the
    expected answer keys. The LLM response is parsed back into a dictionary with
    those keys.
    """

    def __init__(self, system_prompt_path: str, user_template_path: str) -> None:
        self.system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")
        self.user_template = Path(user_template_path).read_text(encoding="utf-8")
        self.client = OllamaClient()
        self.last_prompt: str = ""
        self.last_raw: str = ""

    async def ask(
        self, sections_text: str, question: str, answer_keys: List[str]
    ) -> Dict[str, str]:
        skeleton = OrderedDict((key, "") for key in answer_keys)
        json_skeleton = json.dumps(skeleton, ensure_ascii=False, indent=2)

        user_prompt = self.user_template.format(
            sections_text=sections_text[:100000],
            question=question.strip(),
            json_skeleton=json_skeleton,
        )
        self.last_prompt = normalize_whitespace(user_prompt)

        raw = await self.client.chat(
            self.system_prompt,
            user_prompt,
            temperature=CONFIG.temperature,
            max_tokens=CONFIG.max_tokens,
        )
        self.last_raw = raw

        data = self._parse_json(raw)

        merged = {key: "" for key in answer_keys}
        for key in answer_keys:
            if key in data and isinstance(data[key], str):
                merged[key] = data[key]

        return merged

    def _parse_json(self, raw: str) -> Dict[str, str]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = self._extract_inline_json(raw)

        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _extract_inline_json(raw: str) -> Dict[str, str]:
        import re

        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return {}

        try:
            parsed = json.loads(match.group(0))
        except Exception:
            return {}

        return parsed if isinstance(parsed, dict) else {}

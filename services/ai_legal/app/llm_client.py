from __future__ import annotations

import json
from typing import Any, Iterable

import httpx

from .config import get_settings
from .schemas import LlmDebugInfo


class OllamaClient:
    """Async client wrapper around Ollama endpoints."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        num_ctx: int | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self.num_ctx = num_ctx if num_ctx is not None else settings.ollama_num_ctx

    async def chat(self, messages: Iterable[dict[str, str]], *, model: str | None = None) -> dict[str, Any]:
        """Send a chat completion request to Ollama and return the raw JSON response."""
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": list(messages),
            "stream": False,
            "options": {"temperature": 0, "seed": 123},
        }
        if self.num_ctx:
            payload["options"]["num_ctx"] = self.num_ctx

        settings = get_settings()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(settings.ollama_chat_url, json=payload)
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> dict[str, Any]:
        """List available Ollama models to expose in the health endpoint."""
        settings = get_settings()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(settings.ollama_tags_url)
            response.raise_for_status()
            return response.json()


def extract_reply(data: dict[str, Any]) -> str:
    """Pull the text content from an Ollama response payload."""
    message = data.get("message") if isinstance(data, dict) else None
    if isinstance(message, dict):
        content = message.get("content") or message.get("text")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            joined = "\n".join(str(part) for part in content)
            return joined.strip()
    fallback = data.get("response") or data.get("reply") if isinstance(data, dict) else ""
    return str(fallback or "").strip()


def build_debug_info(messages: list[dict[str, str]], raw: dict[str, Any]) -> LlmDebugInfo:
    """Capture formatted prompt/response pairs for rendering in the HTML report."""
    return LlmDebugInfo(
        prompt=messages,
        prompt_formatted=json.dumps(messages, ensure_ascii=False, indent=2),
        response=raw,
        response_formatted=json.dumps(raw, ensure_ascii=False, indent=2),
    )


client = OllamaClient()


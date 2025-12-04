from typing import Optional

import httpx
from httpx import HTTPStatusError, HTTPError
from ..core.config import CONFIG


class OllamaServiceError(RuntimeError):
    """Raised when the Ollama service cannot be reached or returns an error."""


def _summarize_http_error(exc: HTTPStatusError, endpoint: str) -> str:
    """Return a short human readable description for HTTP failures."""

    response = exc.response
    reason = response.reason_phrase or "Unknown error"
    body = (response.text or "").strip()

    if body and len(body) > 200:
        body = f"{body[:197]}..."

    details = f"HTTP {response.status_code} while calling {endpoint}: {reason}"
    if body:
        details = f"{details}. Response body: {body}"

    return (
        "The Ollama service responded with an unexpected error. "
        f"{details}."
    )

class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or CONFIG.ollama_host
        self.model = model or CONFIG.model_name
        self.num_ctx = CONFIG.num_ctx

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        options = {
            "temperature": temperature if temperature is not None else CONFIG.temperature,
            "num_predict": max_tokens if max_tokens is not None else CONFIG.max_tokens,
        }

        if self.num_ctx:
            options["num_ctx"] = self.num_ctx

        timeout = httpx.Timeout(
            timeout=CONFIG.ollama_read_timeout + 10.0,
            connect=10.0,
            read=CONFIG.ollama_read_timeout,
        )
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout) as client:
            chat_payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": options,
            }

            try:
                response = await client.post("/api/chat", json=chat_payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
            except httpx.ReadTimeout as exc:
                raise OllamaServiceError(
                    "Timed out waiting for a response from the Ollama service. "
                    "Consider increasing OLLAMA_READ_TIMEOUT or checking the model performance."
                ) from exc
            except httpx.ConnectError as exc:
                raise OllamaServiceError(
                    "Unable to connect to the Ollama service at "
                    # f"{self.base_url}. Ensure the service is running at http://ollama_ext:11434."
                    f"{self.base_url}. Ensure the service is running at http://ollama:11434."
                ) from exc
            except HTTPStatusError as exc:
                if exc.response.status_code != 404:
                    raise OllamaServiceError(_summarize_http_error(exc, "/api/chat")) from exc
            except HTTPError as exc:
                raise OllamaServiceError(
                    "Unexpected error while communicating with the Ollama service. "
                    f"{exc}"
                ) from exc

            # Fallback для старых версий Ollama без /api/chat
            generate_payload = {
                "model": self.model,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False,
                "options": options,
            }

            try:
                response = await client.post("/api/generate", json=generate_payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
            except httpx.ReadTimeout as exc:
                raise OllamaServiceError(
                    "Timed out waiting for a response from the Ollama service while using the fallback API."
                ) from exc
            except httpx.ConnectError as exc:
                raise OllamaServiceError(
                    "Unable to connect to the Ollama service at "
                    f"{self.base_url} when using the fallback API. Ensure the service "
                    # "is running at http://ollama_ext:11434."
                    "is running at http://ollama:11434."
                ) from exc
            except HTTPStatusError as exc:
                raise OllamaServiceError(
                    _summarize_http_error(exc, "/api/generate")
                ) from exc
            except HTTPError as exc:
                raise OllamaServiceError(
                    "Unexpected error while communicating with the Ollama service during the fallback request. "
                    f"{exc}"
                ) from exc

    async def list_models(self):
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            try:
                r = await client.get("/api/tags")
                r.raise_for_status()
                return r.json()
            except httpx.ReadTimeout as exc:
                raise OllamaServiceError(
                    "Timed out while requesting the model list from the Ollama service."
                ) from exc
            except httpx.ConnectError as exc:
                raise OllamaServiceError(
                    "Unable to connect to the Ollama service at "
                    f"{self.base_url} when requesting the model list. Ensure the service "
                    # "is running at http://ollama_ext:11434."
                    "is running at http://ollama:11434."
                ) from exc
            except HTTPStatusError as exc:
                raise OllamaServiceError(
                    _summarize_http_error(exc, "/api/tags")
                ) from exc
            except HTTPError as exc:
                raise OllamaServiceError(
                    "Unexpected error while requesting the model list from the Ollama service. "
                    f"{exc}"
                ) from exc

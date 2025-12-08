from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .config import Settings


@dataclass
class ServiceResult:
    """Uniform envelope for downstream service calls."""
    service: str
    url: Optional[str]
    status: Optional[int]
    response: Any
    error: Optional[str]

    @property
    def payload(self) -> Dict[str, Any]:
        """Return structured response data or a normalized error object."""
        if self.response is not None:
            return self.response
        return {"error": self.error, "status": self.status}


class BaseServiceClient:
    """Base class for thin HTTP clients with shared parsing helpers."""
    def __init__(self, settings: Settings, name: str, url: Optional[str] = None) -> None:
        self.settings = settings
        self.name = name
        self.url = url

    @staticmethod
    def _parse_response_payload(response: httpx.Response) -> Any:
        """Try to parse JSON; fall back to raw text for troubleshooting."""
        try:
            return response.json()
        except Exception:
            return response.text


class AiEconomClient(BaseServiceClient):
    """Uploads parsed sections to the ai_econom service for budget analysis."""
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings=settings, name="ai_econom", url=settings.ai_econom_url)

    async def analyze(self, client: httpx.AsyncClient, sections_path: Path) -> ServiceResult:
        """Send the sections.json file to ai_econom and return a normalized result."""
        if not sections_path.exists():
            return ServiceResult(
                service=self.name,
                url=self.url,
                status=None,
                response=None,
                error=f"Sections file not found at {sections_path}",
            )

        files = {
            "spec_file": (
                sections_path.name,
                sections_path.open("rb"),
                "application/json",
            ),
        }

        try:
            response = await client.post(self.url, files=files)
            status = response.status_code
            payload = (
                self._parse_response_payload(response)
                if status == 200
                else None
            )
            error = None if status == 200 else response.text
            return ServiceResult(
                service=self.name,
                url=self.url,
                status=status,
                response=payload,
                error=error,
            )
        except Exception as exc:  # pragma: no cover - external dependency
            return ServiceResult(
                service=self.name,
                url=self.url,
                status=None,
                response=None,
                error=str(exc),
            )
        finally:
            try:
                files["spec_file"][1].close()
            except Exception:
                pass


class AiLegalClient(BaseServiceClient):
    """Uploads parsed sections to the ai_legal service for legal review."""
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings=settings, name="ai_legal", url=settings.ai_legal_url)

    async def analyze(self, client: httpx.AsyncClient, sections_path: Path) -> ServiceResult:
        """Send the sections.json file to ai_legal and return a normalized result."""
        if not sections_path.exists():
            return ServiceResult(
                service=self.name,
                url=self.url,
                status=None,
                response=None,
                error=f"Sections file not found at {sections_path}",
            )

        files = {
            "file": (
                sections_path.name,
                sections_path.open("rb"),
                "application/json",
            ),
        }

        try:
            response = await client.post(self.url, files=files)
            status = response.status_code
            payload = (
                self._parse_response_payload(response)
                if status == 200
                else None
            )
            error = None if status == 200 else response.text
            return ServiceResult(
                service=self.name,
                url=self.url,
                status=status,
                response=payload,
                error=error,
            )
        except Exception as exc:  # pragma: no cover - external dependency
            return ServiceResult(
                service=self.name,
                url=self.url,
                status=None,
                response=None,
                error=str(exc),
            )
        finally:
            try:
                files["file"][1].close()
            except Exception:
                pass


class ContractExtractorClient(BaseServiceClient):
    """Tries multiple contract_extractor endpoints until one succeeds."""
    def __init__(self, settings: Settings) -> None:
        super().__init__(
            settings=settings,
            name="contract_extractor",
            url=None,
        )

    async def extract(self, client: httpx.AsyncClient, payload: Dict[str, Any]) -> ServiceResult:
        """Call contract_extractor with the provided sections payload, rotating URLs on failure."""
        errors: list[str] = []
        for url in self.settings.contract_extractor_urls:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"accept": "application/json", "content-type": "application/json"},
                )
                status = response.status_code
                if status == 200:
                    return ServiceResult(
                        service=self.name,
                        url=url,
                        status=status,
                        response=self._parse_response_payload(response),
                        error=None,
                    )

                errors.append(f"{url}: {status} {response.text}")
            except Exception as exc:  # pragma: no cover - external dependency
                errors.append(f"{url}: {exc}")

        error_message = None
        if errors:
            error_message = f"All connection attempts failed ({'; '.join(errors)})"

        return ServiceResult(
            service=self.name,
            url=None,
            status=None,
            response=None,
            error=error_message,
        )

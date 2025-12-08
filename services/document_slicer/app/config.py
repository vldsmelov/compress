from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Settings:
    """Centralized configuration for the document slicer service."""

    rabbitmq_url: str = field(default_factory=lambda: os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/"))
    upload_queue: str = field(default_factory=lambda: os.getenv("DOC_UPLOAD_QUEUE", "doc_upload"))
    ai_legal_queue: str = field(default_factory=lambda: os.getenv("AI_LEGAL_QUEUE", "ai_legal_parts"))
    ai_econom_queue: str = field(default_factory=lambda: os.getenv("AI_ECONOM_QUEUE", "ai_econom_parts"))
    contract_extractor_queue: str = field(default_factory=lambda: os.getenv("CONTRACT_EXTRACTOR_QUEUE", "contract_extractor_parts"))
    aggregation_queue: str = field(default_factory=lambda: os.getenv("AGGREGATION_QUEUE", "aggregation_tasks"))

    ai_econom_sections: List[str] = field(default_factory=lambda: ["part_16"])

    contract_extractor_sections: List[str] = field(
        default_factory=lambda: [
            "part_4",
            "part_5",
            "part_6",
            "part_7",
            "part_11",
            "part_12",
            "part_15",
            "part_16",
        ]
    )

    ai_econom_url: str = field(
        default_factory=lambda: os.getenv(
            "AI_ECONOM_SERVICE_URL", "http://ai_econom:10000/analyze"
        )
    )
    ai_legal_url: str = field(
        default_factory=lambda: os.getenv(
            "AI_LEGAL_SERVICE_URL", "http://ai_legal:8000/api/sections/full-prepared"
        )
    )
    contract_extractor_base_url: str = field(
        default_factory=lambda: os.getenv(
            "CONTRACT_EXTRACTOR_BASE_URL", "http://contract_extractor:8085"
        )
    )
    contract_extractor_dev_url: str = field(
        default_factory=lambda: os.getenv(
            "CONTRACT_EXTRACTOR_DEV_BASE_URL", "http://contract_extractor:8000"
        )
    )
    legacy_contract_extractor_url: str = field(
        default_factory=lambda: os.getenv(
            "CONTRACT_EXTRACTOR_URL",
            "http://contract_extractor:8085/qa/sections?plan=default",
        )
    )
    http_timeout: float = field(
        default_factory=lambda: float(os.getenv("SERVICE_HTTP_TIMEOUT", "120"))
    )
    data_volume_path: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_VOLUME_PATH", "/data"))
    )
    sections_file_name: str = field(
        default_factory=lambda: os.getenv("SECTIONS_FILE_NAME", "sections.json")
    )
    part_16_file_name: str = field(
        default_factory=lambda: os.getenv("PART_16_FILE_NAME", "part_16.json")
    )

    contract_extractor_sections_legacy: List[str] = field(
        default_factory=lambda: [
            "part_4",
            "part_5",
            "part_6",
            "part_7",
            "part_11",
            "part_12",
            "part_15",
            "part_16",
        ]
    )

    @property
    def sections_path(self) -> Path:
        return self.data_volume_path / self.sections_file_name

    @property
    def part_16_path(self) -> Path:
        raw = os.getenv("PART_16_FILE_PATH")
        if raw:
            return Path(raw)
        return self.data_volume_path / self.part_16_file_name

    @property
    def contract_extractor_sections(self) -> List[str]:
        return self.contract_extractor_sections_legacy

    @property
    def contract_extractor_urls(self) -> List[str]:
        raw_urls = os.getenv("CONTRACT_EXTRACTOR_URLS", "")
        explicit_urls = [url.strip() for url in raw_urls.split(",") if url.strip()]

        fallback_base = "http://localhost:8085"
        fallback_legacy = "http://localhost:8085/qa/sections?plan=default"

        base_candidates = [
            self.contract_extractor_base_url,
            fallback_base,
            self.contract_extractor_dev_url,
            "http://localhost:8000",
        ]

        legacy_candidates = [self.legacy_contract_extractor_url, fallback_legacy]

        urls: list[str] = []
        seen: set[str] = set()

        def _add_url(url: str) -> None:
            if url and url not in seen:
                seen.add(url)
                urls.append(url)

        for candidate in [*explicit_urls, *base_candidates, *legacy_candidates]:
            if not candidate:
                continue

            trimmed = candidate.strip().rstrip("/")

            if "/qa/" in trimmed or "plan=" in trimmed:
                _add_url(trimmed)
                continue

            for suffix in ("/qa/run-default", "/qa/sections?plan=default"):
                _add_url(f"{trimmed}{suffix}")

        return urls

    def ensure_data_dir(self) -> None:
        self.data_volume_path.mkdir(parents=True, exist_ok=True)

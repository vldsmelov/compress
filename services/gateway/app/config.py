from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    rabbitmq_url: str = field(default_factory=lambda: os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/"))
    upload_queue: str = field(default_factory=lambda: os.getenv("DOC_UPLOAD_QUEUE", "doc_upload"))
    response_timeout: float = field(default_factory=lambda: float(os.getenv("GATEWAY_RESPONSE_TIMEOUT", "300")))

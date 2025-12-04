from fastapi import FastAPI

from ..routes.extraction import router as extraction_router
from ..handlers.extraction import ensure_qa_service
from .core.config import CONFIG

app = FastAPI(title="Contract Extractor API", version=CONFIG.version)

if CONFIG.use_llm:
    ensure_qa_service()

app.include_router(extraction_router)


__all__ = ["app"]

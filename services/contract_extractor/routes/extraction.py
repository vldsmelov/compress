from fastapi import APIRouter, File, Query, UploadFile

from ..handlers.extraction import ensure_qa_service, qa_docx

router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.post("/qa/docx")
async def qa_docx_route(file: UploadFile = File(...), plan: str = Query("default")):
    return await qa_docx(file, plan)


__all__ = ["router", "ensure_qa_service"]

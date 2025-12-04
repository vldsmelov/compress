import json
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..handlers.extraction import ensure_qa_service, qa_sections


class SectionsPayload(BaseModel):
    sections: dict[str, Any] | list[Any]


router = APIRouter()


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.post("/qa/sections")
async def qa_sections_route(payload: SectionsPayload, plan: str = Query("default")):
    return await qa_sections(payload.sections, plan)


@router.post("/qa/run-default")
async def qa_run_default(payload: SectionsPayload):
    """Run QA using the built-in ``default`` plan against the provided sections."""

    return await qa_sections(payload.sections, "default")


@router.get("/qa/sample-payload")
async def qa_sample_payload():
    """Provide a minimal payload that the /qa/sections endpoint accepts."""

    sample_sections = {
        "part_4": "Оплата производится 100% по факту поставки.",
        "part_5": "Ответственный: Иванов Иван Иванович, менеджер проекта.",
        "part_6": "Поставщик обязуется предоставить оборудование в срок.",
        "part_7": "Контроль качества выполняется покупателем.",
        "part_11": "Срок действия договора до 31.12.2025.",
        "part_12": "Иные условия поставки.",
        "part_15": "Стороны: ООО Покупатель и ООО Продавец.",
        "part_16": "Товары поставляются на сумму 1 000 000 RUB с НДС 20%.",
    }

    curl_command = " ".join(
        [
            "curl -X POST",
            "\"http://localhost:8085/qa/sections?plan=default\"",
            "-H",
            "'Content-Type: application/json'",
            "-d",
            "'" + json.dumps({"sections": sample_sections}, ensure_ascii=False) + "'",
        ]
    )

    return {
        "plan": "default",
        "sections": sample_sections,
        "curl": curl_command,
        "note": "POST the JSON above to /qa/sections to verify connectivity without uploading files.",
    }


__all__ = ["router", "ensure_qa_service"]

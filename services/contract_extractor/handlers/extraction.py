from functools import lru_cache
from typing import Any, Dict, List

from fastapi import HTTPException

from ..app.core.config import get_settings
from ..app.pipeline import QAPlanLoader, QAPlanPipeline
from ..app.services.qa import SectionQuestionAnswering
from ..app.services.sb_check_service import get_sb_check_service


@lru_cache()
def _get_pipeline() -> QAPlanPipeline:
    settings = get_settings()
    qa_service = (
        SectionQuestionAnswering(
            str(settings.qa_system_prompt), str(settings.qa_user_template), settings
        )
        if settings.use_llm
        else None
    )
    plan_loader = QAPlanLoader(settings.qa_plans_dir)
    sb_service = get_sb_check_service()
    return QAPlanPipeline(settings, plan_loader, qa_service, sb_service)


def ensure_qa_service():
    pipeline = _get_pipeline()
    if pipeline.qa_service is None:
        raise HTTPException(status_code=503, detail="LLM features are disabled (USE_LLM=false)")
    return pipeline.qa_service


async def qa_sections(sections: Dict[str, Any] | List[Any], plan: str):
    pipeline = _get_pipeline()
    return await pipeline.run(sections, plan)


__all__ = ["qa_sections", "ensure_qa_service"]

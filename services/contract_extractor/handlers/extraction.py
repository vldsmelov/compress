import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException

from ..app.core.config import CONFIG
from ..app.services.ollama_client import OllamaServiceError
from ..app.services.qa import SectionQuestionAnswering

APP_DIR = Path(__file__).resolve().parent.parent / "app"
QA_SYSTEM_PROMPT_PATH = APP_DIR / "prompts" / "qa_system.txt"
QA_USER_TMPL_PATH = APP_DIR / "prompts" / "qa_user_template.txt"
QA_PLANS_DIR = APP_DIR / "assets" / "qa_plans"


@lru_cache()
def get_qa_service():
    return (
        SectionQuestionAnswering(str(QA_SYSTEM_PROMPT_PATH), str(QA_USER_TMPL_PATH))
        if CONFIG.use_llm
        else None
    )


def ensure_qa_service():
    qa_service = get_qa_service()
    if qa_service is None:
        raise HTTPException(status_code=503, detail="LLM features are disabled (USE_LLM=false)")
    return qa_service


def _load_json_file(path: Path):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Requested resource not found") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover
        logging.exception("Invalid JSON content in %s", path)
        raise HTTPException(status_code=500, detail="Invalid JSON content") from exc


def _normalize_queries(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    queries = payload.get("queries") or payload.get("plan") or payload.get("questions")
    if not queries or not isinstance(queries, list):
        raise HTTPException(status_code=400, detail="Provide a non-empty 'queries' list")

    normalized: List[Dict[str, Any]] = []
    for item in queries:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Each query must be an object")

        parts = item.get("parts")
        question = item.get("question")
        answers = item.get("answer")

        if not isinstance(parts, list) or not all(isinstance(p, str) for p in parts):
            raise HTTPException(status_code=400, detail="Query 'parts' must be a list of strings")
        if not isinstance(question, str) or not question.strip():
            raise HTTPException(status_code=400, detail="Query 'question' must be a non-empty string")
        if not isinstance(answers, list) or not all(isinstance(a, str) for a in answers):
            raise HTTPException(status_code=400, detail="Query 'answer' must be a list of strings")

        normalized.append({"parts": parts, "question": question.strip(), "answer": answers})

    return normalized


def _load_qa_plan(plan_name: str) -> List[Dict[str, Any]]:
    safe_name = Path(plan_name).stem
    plan_path = QA_PLANS_DIR / f"{safe_name}.json"

    if not plan_path.exists():
        raise HTTPException(status_code=404, detail=f"QA plan '{safe_name}' not found")

    content = _load_json_file(plan_path)
    plan_payload = {"queries": content} if isinstance(content, list) else content

    if not isinstance(plan_payload, dict):
        raise HTTPException(status_code=400, detail="QA plan must be an object or array of queries")

    return _normalize_queries(plan_payload)


async def _run_queries(sections_map: Dict[str, str], queries: List[Dict[str, Any]]):
    qa_service = ensure_qa_service()
    aggregated: Dict[str, Any] = {}
    responses: List[Dict[str, Any]] = []

    for query in queries:
        missing_parts = [name for name in query["parts"] if name not in sections_map]
        if missing_parts:
            raise HTTPException(
                status_code=400,
                detail=f"Sections not found for parts: {', '.join(sorted(set(missing_parts)))}",
            )

        combined_text = "\n\n".join(sections_map[name] for name in query["parts"])
        result = await qa_service.ask(combined_text, query["question"], query["answer"])

        responses.append({"question": query["question"], "parts": query["parts"], "result": result})
        for key, value in result.items():
            aggregated[key] = value

    return {"ok": True, "result": aggregated, "responses": responses}


async def _attach_sb_check(payload: Dict[str, Any]) -> Dict[str, Any]:
    sb_payload = {
        "status": 0,
        "company_name": "",
        "globas_score": None,
        "good_count": 0,
        "bad_count": 0,
        "html_report": "",
    }

    seller_name = None
    try:
        seller_name = payload.get("result", {}).get("seller")
    except Exception:
        seller_name = None

    if seller_name and isinstance(seller_name, str) and seller_name.strip():
        try:
            from ..app.services.sb_check_service import get_sb_check_service

            service = get_sb_check_service()
            sb_result = await service.analyze_company(seller_name)

            sb_payload = {
                "status": 1,
                "company_name": sb_result.company_name,
                "globas_score": sb_result.globas_score,
                "good_count": sb_result.good_count,
                "bad_count": sb_result.bad_count,
                "html_report": sb_result.html_report,
            }

        except ValueError:
            logging.warning("SB Check: company '%s' not found", seller_name)
        except Exception as exc:  # pragma: no cover - defensive guard
            logging.exception("SB Check analysis failed: %s", exc)

    payload["sb_ai"] = sb_payload
    return payload


def _normalize_sections_map(sections: Dict[str, Any]) -> Dict[str, str]:
    if not sections:
        raise HTTPException(status_code=400, detail="Provide non-empty sections payload")

    if isinstance(sections, list):
        return {f"part_{idx}": str(value) for idx, value in enumerate(sections)}

    normalized: Dict[str, str] = {}
    for key, value in sections.items():
        if not isinstance(key, str):
            raise HTTPException(status_code=400, detail="Section keys must be strings")
        if value is None:
            continue
        normalized[key] = str(value)

    if not normalized:
        raise HTTPException(status_code=400, detail="No sections to process")

    return normalized


async def qa_sections(sections: Dict[str, Any], plan: str):
    ensure_qa_service()

    normalized_sections = _normalize_sections_map(sections)
    queries = _load_qa_plan(plan)

    try:
        qa_result = await _run_queries(normalized_sections, queries)
    except OllamaServiceError as exc:
        logging.exception("Ollama service error during QA plan execution")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        logging.exception("Unhandled error during QA plan execution")
        raise HTTPException(status_code=500, detail="Internal processing error") from exc

    await _attach_sb_check(qa_result)
    return qa_result


__all__ = [
    "qa_sections",
    "ensure_qa_service",
]

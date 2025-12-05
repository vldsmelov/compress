from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from .core.config import Settings
from .services.ollama_client import OllamaServiceError
from .services.qa import SectionQuestionAnswering
from .services.sb_check_service import SBCheckService

logger = logging.getLogger(__name__)


class QAPlanLoader:
    """Loader that validates and normalizes QA plans stored on disk."""

    def __init__(self, plans_dir: Path):
        self.plans_dir = Path(plans_dir)

    def load(self, plan_name: str) -> List[Dict[str, Any]]:
        safe_name = Path(plan_name).stem
        plan_path = self.plans_dir / f"{safe_name}.json"

        if not plan_path.exists():
            raise HTTPException(status_code=404, detail=f"QA plan '{safe_name}' not found")

        content = self._read_json(plan_path)
        plan_payload = {"queries": content} if isinstance(content, list) else content

        if not isinstance(plan_payload, dict):
            raise HTTPException(status_code=400, detail="QA plan must be an object or array of queries")

        return self._normalize_queries(plan_payload)

    @staticmethod
    def _read_json(path: Path) -> Any:
        try:
            with path.open("r", encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError as exc:  # pragma: no cover - guarded by exists
            raise HTTPException(status_code=404, detail="Requested resource not found") from exc
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
            logger.exception("Invalid JSON content in %s", path)
            raise HTTPException(status_code=500, detail="Invalid JSON content") from exc

    @staticmethod
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


class QAPlanPipeline:
    """Pipeline that executes QA plans against provided contract sections."""

    def __init__(
        self,
        settings: Settings,
        plan_loader: QAPlanLoader,
        qa_service: Optional[SectionQuestionAnswering],
        sb_service: Optional[SBCheckService] = None,
    ) -> None:
        self.settings = settings
        self.plan_loader = plan_loader
        self.qa_service = qa_service
        self.sb_service = sb_service

    async def run(self, sections: Dict[str, Any] | List[Any], plan: str) -> Dict[str, Any]:
        """Execute the requested QA plan and attach optional SB-check results."""
        normalized_sections = self._normalize_sections(sections)
        queries = self.plan_loader.load(plan)
        plan_parts = self._collect_plan_parts(queries)
        filtered_sections = {k: v for k, v in normalized_sections.items() if k in plan_parts}

        if not filtered_sections:
            raise HTTPException(status_code=400, detail="No contract sections match the QA plan")

        if self.qa_service is None:
            qa_result = self._build_empty_result(queries)
        else:
            try:
                qa_result = await self._run_queries(filtered_sections, queries)
            except OllamaServiceError as exc:
                logger.exception("Ollama service error during QA plan execution")
                qa_result = self._build_empty_result(queries)
                qa_result["error"] = str(exc)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("Unhandled error during QA plan execution")
                qa_result = self._build_empty_result(queries)
                qa_result["error"] = "Internal processing error"

        await self._attach_sb_check(qa_result)
        return qa_result

    async def _run_queries(
        self, sections_map: Dict[str, str], queries: Iterable[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ask the LLM questions for each plan entry and aggregate answers."""
        qa_service = self.qa_service
        if qa_service is None:
            raise HTTPException(status_code=503, detail="LLM features are disabled")

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

    @staticmethod
    def _collect_plan_parts(queries: Iterable[Dict[str, Any]]) -> set[str]:
        """Collect all part names referenced across QA queries."""
        parts: set[str] = set()
        for query in queries:
            parts.update(query.get("parts", []))
        return parts

    @staticmethod
    def _normalize_sections(sections: Dict[str, Any] | List[Any]) -> Dict[str, str]:
        """Coerce incoming sections into a consistent mapping of part_* to strings."""
        if not sections:
            raise HTTPException(status_code=400, detail="Provide non-empty sections payload")

        if isinstance(sections, list):
            normalized = {f"part_{idx}": str(value) for idx, value in enumerate(sections)}
        elif isinstance(sections, dict):
            normalized = {k: str(v) for k, v in sections.items() if v is not None and isinstance(k, str)}
        else:
            raise HTTPException(status_code=400, detail="Sections payload must be an object or array")

        if not normalized:
            raise HTTPException(status_code=400, detail="No sections to process")

        return normalized

    @staticmethod
    def _build_empty_result(queries: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """Return placeholders when LLM processing is disabled or fails."""
        aggregated: Dict[str, Any] = {}
        responses: List[Dict[str, Any]] = []

        for query in queries:
            skeleton = {key: "" for key in query.get("answer", [])}
            aggregated.update(skeleton)
            responses.append(
                {
                    "question": query.get("question", ""),
                    "parts": query.get("parts", []),
                    "result": skeleton,
                    "note": "LLM unavailable, returned empty placeholders",
                }
            )

        return {"ok": False, "result": aggregated, "responses": responses}

    async def _attach_sb_check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich the QA result with SB-check findings when a seller is present."""
        if not self.sb_service:
            return payload

        sb_payload = {
            "status": 0,
            "status_reason": "seller not provided",
            "company_name": "",
            "globas_score": None,
            "good_count": 0,
            "bad_count": 0,
            "html_report": "",
        }

        try:
            seller_name = payload.get("result", {}).get("seller")
        except Exception:  # pragma: no cover - defensive guard
            seller_name = None

        if seller_name and isinstance(seller_name, str) and seller_name.strip():
            sb_payload["company_name"] = seller_name
            sb_payload["status_reason"] = "seller not found"
            try:
                sb_result = await self.sb_service.analyze_company(seller_name)
                sb_payload = {
                    "status": 1,
                    "status_reason": "seller matched",
                    "company_name": sb_result.company_name,
                    "globas_score": sb_result.globas_score,
                    "good_count": sb_result.good_count,
                    "bad_count": sb_result.bad_count,
                    "html_report": sb_result.html_report,
                }
            except ValueError:
                logger.warning("SB Check: company '%s' not found", seller_name)
                sb_payload["status"] = -1
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.exception("SB Check analysis failed: %s", exc)

        payload["sb_ai"] = sb_payload
        return payload


__all__ = ["QAPlanLoader", "QAPlanPipeline"]

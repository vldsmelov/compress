from __future__ import annotations

import asyncio
import time
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from .document.reader import load_blocks
from .document.spec_extractor import extract_specification_from_blocks
from .services.section_splitter import SectionChunk, split_into_sections

app = FastAPI(title="Document Splitter Service", version="0.1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

subscribers: List[asyncio.Queue] = []

@app.get("/api/timer/events")
async def timer_events():
    """
    Все открывшие /timer.html подключаются сюда.
    """
    queue: asyncio.Queue = asyncio.Queue()
    subscribers.append(queue)

    async def event_stream():
        try:
            while True:
                msg = await queue.get()
                yield f"event: {msg['event']}\ndata: {msg['time']}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            subscribers.remove(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


async def broadcast(event: str, timestamp: float):
    """
    Рассылает событие всем слушателям /api/timer/events
    """
    data = {"event": event, "time": timestamp}
    for q in subscribers:
        await q.put(data)


AI_ECONOM_SERVICE_URL = os.getenv("AI_ECONOM_SERVICE_URL", "http://ai_econom:10000/analyze")
AI_LEGAL_SERVICE_URL = os.getenv(
    "AI_LEGAL_SERVICE_URL", "http://ai_legal:8000/api/sections/full-prepared"
)
CONTRACT_EXTRACTOR_URL = os.getenv(
    "CONTRACT_EXTRACTOR_URL", "http://contract_extractor:8085/qa/sections?plan=default"
)
CONTRACT_EXTRACTOR_SECTIONS = [
    "part_4",
    "part_5",
    "part_6",
    "part_7",
    "part_11",
    "part_12",
    "part_15",
    "part_16",
]

HTTP_TIMEOUT = float(os.getenv("SERVICE_HTTP_TIMEOUT", "120"))
DATA_VOLUME_PATH = Path(os.getenv("DATA_VOLUME_PATH", "/data"))
SECTIONS_FILE_NAME = os.getenv("SECTIONS_FILE_NAME", "sections.json")
PART_16_FILE_NAME = os.getenv("PART_16_FILE_NAME", "part_16.json")
PART_16_FILE_PATH = Path(
    os.getenv("PART_16_FILE_PATH", str(DATA_VOLUME_PATH / "part_16.json"))
)

def _section_to_text(section: SectionChunk) -> str:
    parts = [section.title.strip()] if section.title else []
    if section.content:
        parts.append(section.content.strip())
    return "\n".join(part for part in parts if part)


def _serialize_parts(sections: list[SectionChunk], blocks_html: str) -> dict[str, str]:
    payload: dict[str, str] = {f"part_{index}": "" for index in range(17)}

    for section in sections:
        if section.number is None:
            key = "part_0"
        elif 1 <= section.number <= 15:
            key = f"part_{section.number}"
        else:
            continue

        section_text = _section_to_text(section)
        if not section_text:
            continue

        existing = payload.get(key, "")
        payload[key] = "\n\n".join(
            value for value in (existing.strip(), section_text) if value
        )

    payload["part_16"] = blocks_html.strip()

    return payload


def _select_contract_sections(parts: dict[str, str]) -> dict[str, str]:
    return {key: parts.get(key, "") for key in CONTRACT_EXTRACTOR_SECTIONS}


def _extract_specification_text(blocks: list[Any]) -> str:
    try:
        spec_result = extract_specification_from_blocks(blocks)
        lines = []
        for table_region in spec_result.tables:
            for row in table_region.block.rows or []:
                row_text = " | ".join(cell.strip() for cell in row)
                lines.append(f"TABLE: {row_text}")

        return "\n".join(lines)
    except Exception:
        return ""


async def _read_upload_file(file: UploadFile) -> tuple[str, bytes]:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл пуст или не содержит данных")
    filename = file.filename or "document.docx"
    content_type = (
        file.content_type
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return filename, content_type, content



def _extract_parts(file_name: str, content: bytes) -> dict[str, str]:

    try:
        blocks = load_blocks(file_name, content)
    except Exception as exc:  # pragma: no cover - defensive parsing guard
        raise HTTPException(status_code=400, detail=f"Не удалось разобрать файл: {exc}") from exc

    sections = split_into_sections(blocks)
    specification_text = _extract_specification_text(blocks)
    return _serialize_parts(sections, specification_text)


def _persist_sections(parts: dict[str, str]) -> dict[str, Path]:
    DATA_VOLUME_PATH.mkdir(parents=True, exist_ok=True)

    sections_path = DATA_VOLUME_PATH / SECTIONS_FILE_NAME
    part_16_path = DATA_VOLUME_PATH / PART_16_FILE_NAME

    try:
        sections_path.write_text(
            json.dumps(parts, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        part_16_payload = {"part_16": parts.get("part_16", "")}

        part_16_path.write_text(
            json.dumps(part_16_payload, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except OSError:
        # Непринципиально для пользователя; ошибки прокинутся в лог
        pass

    return {"sections": sections_path, "part_16": part_16_path}


def _parse_response_payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text

async def _call_ai_econom_service(
    client: httpx.AsyncClient, sections_file_path: Path
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "service": "ai_econom",
        "url": AI_ECONOM_SERVICE_URL,
        "status": None,
        "response": None,
        "error": None,
    }

    if not sections_file_path.exists():
        result["error"] = f"Sections file not found at {sections_file_path}"
        return result

    files = {
        "spec_file": (
            sections_file_path.name,
            sections_file_path.open("rb"),
            "application/json",
        ),
    }

    try:
        response = await client.post(AI_ECONOM_SERVICE_URL, files=files)
        result["status"] = response.status_code
        if response.status_code == 200:
            result["response"] = _parse_response_payload(response)
        else:
            result["error"] = response.text
    except Exception as exc:  # pragma: no cover - defensive external call guard
        result["error"] = str(exc)
    finally:
        try:
            # files["budget_file"][1].close()
            files["spec_file"][1].close()
        except Exception:
            pass

    return result


async def _call_ai_legal_service(
    client: httpx.AsyncClient, sections_file_path: Path
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "service": "ai_legal",
        "url": AI_LEGAL_SERVICE_URL,
        "status": None,
        "response": None,
        "error": None,
    }

    if not sections_file_path.exists():
        result["error"] = f"Sections file not found at {sections_file_path}"
        return result

    files = {
        "file": (
            sections_file_path.name,
            sections_file_path.open("rb"),
            "application/json",
        ),
    }

    try:
        primary_response = await client.post(AI_LEGAL_SERVICE_URL, files=files)
        result["status"] = primary_response.status_code
        if primary_response.status_code == 200:
            result["response"] = _parse_response_payload(primary_response)
        else:
            result["error"] = primary_response.text
    except Exception as exc:  # pragma: no cover - defensive external call guard
        result["error"] = str(exc)
    finally:
        try:
            files["file"][1].close()
        except Exception:
            pass

    return result

async def _call_contract_extractor_service(
    client: httpx.AsyncClient, parts: Dict[str, str]
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "service": "contract_extractor",
        "url": CONTRACT_EXTRACTOR_URL,
        "status": None,
        "response": None,
        "error": None,
    }

    try:
        response = await client.post(
            CONTRACT_EXTRACTOR_URL,
            json={"sections": _select_contract_sections(parts)},
            headers={"accept": "application/json"},
        )
        result["status"] = response.status_code
        if response.status_code == 200:
            result["response"] = _parse_response_payload(response)
        else:
            result["error"] = response.text
    except Exception as exc:  # pragma: no cover - defensive external call guard
        result["error"] = str(exc)

    return result

@app.post("/api/sections/split")
async def split_document(file: UploadFile = File(...)) -> JSONResponse:
    file_name, _, content = await _read_upload_file(file)
    parts = _extract_parts(file_name, content)
    _persist_sections(parts)
    return JSONResponse(content=parts)


@app.post("/test/")
async def test_split_document(file: UploadFile = File(...)) -> JSONResponse:
    file_name, _, content = await _read_upload_file(file)
    parts = _extract_parts(file_name, content)
    return JSONResponse(content=parts)


@app.post("/api/sections/dispatch")
async def dispatch_sections(file: UploadFile = File(...)) -> JSONResponse:
    
    start = time.time()
    await broadcast("start", start)

    file_name, _, content = await _read_upload_file(file)
    parts = _extract_parts(file_name, content)
    saved_paths = _persist_sections(parts)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, trust_env=False) as client:
        ai_econom_task = asyncio.create_task(
            _call_ai_econom_service(client, saved_paths["sections"])
        )
        ai_legal_task = asyncio.create_task(
            _call_ai_legal_service(client, saved_paths["sections"])
        )
        contract_extractor_task = asyncio.create_task(
            _call_contract_extractor_service(client, parts)
        )
        service_results = await asyncio.gather(
            ai_econom_task, ai_legal_task, contract_extractor_task
        )

    responses: dict[str, Any] = {
        "ai_econom": None,
        "ai_legal": None,
        "sb_ai": None,
        "contract_extractor": None,
    }

    for result in service_results:
        payload = (
            result.get("response")
            if result.get("response") is not None
            else {"error": result.get("error"), "status": result.get("status")}
        )
        if result["service"] == "contract_extractor":
            contract_payload = payload
            sb_payload = payload
            if isinstance(payload, dict):
                contract_payload = payload.get("result", payload)
                sb_payload = payload.get("sb_ai", payload)

            responses["contract_extractor"] = contract_payload
            responses["sb_ai"] = sb_payload
        else:
            responses[result["service"]] = payload

    for key in ("ai_econom", "ai_legal", "sb_ai", "contract_extractor"):
        if responses[key] is None:
            responses[key] = {}

    stop = time.time()
    await broadcast("stop", stop)

    return JSONResponse(content=responses)


@app.get("/time")
async def time_page():
    return FileResponse("static/time.html")

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

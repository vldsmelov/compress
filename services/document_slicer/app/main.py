from __future__ import annotations

import asyncio
import time
from typing import List

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .pipeline import DocumentPipeline

app = FastAPI(title="Document Splitter Service", version="0.1.0")
settings = Settings()
pipeline = DocumentPipeline(settings=settings)

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
    """Потоковое подключение для вывода прогресса обработки."""
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
    """Рассылает событие всем слушателям /api/timer/events."""
    data = {"event": event, "time": timestamp}
    for q in subscribers:
        await q.put(data)


@app.post("/api/sections/split")
async def split_document(file: UploadFile = File(...)) -> JSONResponse:
    file_name, content = await pipeline.read_upload(file)
    parts = pipeline.extract_parts(file_name, content)
    pipeline.persist_sections(parts)
    return JSONResponse(content=parts)


@app.post("/test")
async def test_split_document(file: UploadFile = File(...)) -> JSONResponse:
    file_name, content = await pipeline.read_upload(file)
    parts = pipeline.extract_parts(file_name, content)
    return JSONResponse(content=parts)


@app.post("/api/sections/dispatch")
async def dispatch_sections(file: UploadFile = File(...)) -> JSONResponse:
    start = time.time()
    await broadcast("start", start)

    file_name, content = await pipeline.read_upload(file)
    parts = pipeline.extract_parts(file_name, content)
    saved_paths = pipeline.persist_sections(parts)

    responses = await pipeline.dispatch(parts=parts, sections_path=saved_paths["sections"])

    stop = time.time()
    await broadcast("stop", stop)

    return JSONResponse(content=responses)


@app.post("/api/dispatcher")
async def dispatch_sections_alias(file: UploadFile = File(...)) -> JSONResponse:
    """Backward-compatible alias for section dispatching."""
    return await dispatch_sections(file)


@app.get("/time")
async def time_page():
    return FileResponse("static/time.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

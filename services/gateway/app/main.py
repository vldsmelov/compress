from __future__ import annotations

import asyncio
import base64
import json
import uuid

import aio_pika
from fastapi import FastAPI, File, HTTPException, UploadFile

from .config import Settings

app = FastAPI(title="Gateway")
settings = Settings()


async def _await_response(correlation_id: str, reply_queue: aio_pika.Queue, timeout: float):
    future = asyncio.get_event_loop().create_future()

    async def _on_message(message: aio_pika.IncomingMessage) -> None:
        if message.correlation_id != correlation_id:
            return
        async with message.process():
            future.set_result(json.loads(message.body.decode()))

    await reply_queue.consume(_on_message, no_ack=False)
    return await asyncio.wait_for(future, timeout=timeout)


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл пуст")

    correlation_id = str(uuid.uuid4())
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        reply_queue = await channel.declare_queue(exclusive=True)

        payload = {
            "task_id": correlation_id,
            "filename": file.filename or "document.docx",
            "content": base64.b64encode(content).decode(),
            "reply_to": reply_queue.name,
        }

        upload_queue = await channel.declare_queue(settings.upload_queue, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode(),
                correlation_id=correlation_id,
                reply_to=reply_queue.name,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=upload_queue.name,
        )

        try:
            response = await _await_response(correlation_id, reply_queue, timeout=settings.response_timeout)
        except asyncio.TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Не дождались ответа от агрегатора") from exc

    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

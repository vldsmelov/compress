from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from typing import Any, Dict

import aio_pika

from .config import Settings
from .pipeline import DocumentPipeline


async def _publish_message(
    channel: aio_pika.Channel,
    queue_name: str,
    payload: Dict[str, Any],
    *,
    correlation_id: str,
    reply_to: str | None,
) -> None:
    queue = await channel.declare_queue(queue_name, durable=True)
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload).encode(),
            correlation_id=correlation_id,
            reply_to=reply_to,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        ),
        routing_key=queue.name,
    )


async def handle_upload(
    message: aio_pika.IncomingMessage,
    *,
    pipeline: DocumentPipeline,
    settings: Settings,
) -> None:
    async with message.process():
        payload = json.loads(message.body.decode())
        correlation_id = message.correlation_id or payload.get("task_id") or str(uuid.uuid4())
        reply_to = message.reply_to or payload.get("reply_to")

        encoded = payload.get("content")
        if not encoded:
            return

        content = base64.b64decode(encoded)
        file_name = payload.get("filename", "document.docx")

        parts = pipeline.extract_parts(file_name, content)
        pipeline.persist_sections(parts)

        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()

            expected_services = ["ai_legal", "ai_econom", "contract_extractor", "sb_ai"]
            await _publish_message(
                channel,
                settings.aggregation_queue,
                {
                    "task_id": correlation_id,
                    "reply_to": reply_to,
                    "expected_services": expected_services,
                },
                correlation_id=correlation_id,
                reply_to=reply_to,
            )

            await _publish_message(
                channel,
                settings.ai_legal_queue,
                {"task_id": correlation_id, "parts": parts},
                correlation_id=correlation_id,
                reply_to=reply_to,
            )

            ai_econom_parts = {key: value for key, value in parts.items() if key in settings.ai_econom_sections}
            await _publish_message(
                channel,
                settings.ai_econom_queue,
                {"task_id": correlation_id, "parts": ai_econom_parts},
                correlation_id=correlation_id,
                reply_to=reply_to,
            )

            contract_parts = {key: value for key, value in parts.items() if key in settings.contract_extractor_sections}
            await _publish_message(
                channel,
                settings.contract_extractor_queue,
                {"task_id": correlation_id, "sections": contract_parts},
                correlation_id=correlation_id,
                reply_to=reply_to,
            )


async def main() -> None:
    settings = Settings()
    pipeline = DocumentPipeline(settings=settings)
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)

    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(settings.upload_queue, durable=True)
        await queue.consume(lambda message: handle_upload(message, pipeline=pipeline, settings=settings))
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

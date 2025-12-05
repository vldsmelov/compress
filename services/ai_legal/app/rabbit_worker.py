from __future__ import annotations

import asyncio
import json
import os

import aio_pika

from .pipeline import pipeline
from .reviews import reviewer


async def handle_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body.decode())
        parts = payload.get("parts")
        if not isinstance(parts, dict):
            return

        prepared = pipeline.prepare_from_payload(parts)
        result = await reviewer.evaluate_sections(
            prepared.combined_text,
            prepared.document_html,
            expected_titles=prepared.titles,
            expected_numbers=prepared.numbers,
        )

        response = {
            "service": "ai_legal",
            "payload": {
                "overall_score": result.overall_score,
                "html": result.html_report,
                "inaccuracy": result.inaccuracy,
                "red_flags": result.red_flags,
            },
        }

        connection = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/"))
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(os.getenv("AGGREGATION_RESULTS_QUEUE", "aggregation_results"), durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(response).encode(),
                    correlation_id=message.correlation_id,
                    reply_to=message.reply_to,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                ),
                routing_key=queue.name,
            )


async def main() -> None:
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")
    queue_name = os.getenv("AI_LEGAL_QUEUE", "ai_legal_parts")

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.consume(handle_message)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

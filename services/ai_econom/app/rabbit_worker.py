from __future__ import annotations

import asyncio
import json
import os

import aio_pika

from .analysis import PurchaseAnalyzer
from .budget_store import BudgetStore
from .config import get_settings
from .llm_client import LlmClient


async def publish(queue_name: str, message: dict, correlation_id: str | None, reply_to: str | None) -> None:
    connection = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/"))
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                correlation_id=correlation_id,
                reply_to=reply_to,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=queue.name,
        )


async def handle_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body.decode())
        parts = payload.get("parts") or {}

        settings = get_settings()
        analyzer = PurchaseAnalyzer(BudgetStore(settings), LlmClient(settings))

        spec_data = analyzer.parse_spec(parts)
        result = analyzer.analyze(spec_data)

        response = {"service": "ai_econom", "payload": result}
        await publish(
            os.getenv("AGGREGATION_RESULTS_QUEUE", "aggregation_results"),
            response,
            message.correlation_id,
            message.reply_to,
        )

        seller = parts.get("part_15") or result.get("seller")
        if seller:
            await publish(
                os.getenv("SB_QUEUE", "sb_queue"),
                {"task_id": message.correlation_id, "seller": seller},
                message.correlation_id,
                message.reply_to,
            )


async def main() -> None:
    rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")
    queue_name = os.getenv("AI_ECONOM_QUEUE", "ai_econom_parts")

    connection = await aio_pika.connect_robust(rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.consume(handle_message)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

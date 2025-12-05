from __future__ import annotations

import asyncio
import json
import os

import aio_pika


async def handle_message(message: aio_pika.IncomingMessage) -> None:
    async with message.process():
        payload = json.loads(message.body.decode())
        seller = payload.get("seller")
        response = {"service": "sb_ai", "payload": {"seller": seller}}

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
    connection = await aio_pika.connect_robust(os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/"))
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(os.getenv("SB_QUEUE", "sb_queue"), durable=True)
        await queue.consume(handle_message)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())

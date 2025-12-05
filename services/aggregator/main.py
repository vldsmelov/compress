from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

import aio_pika


@dataclass
class AggregationState:
    expected: Set[str]
    reply_to: Optional[str]
    results: Dict[str, Any] = field(default_factory=dict)


class Aggregator:
    def __init__(self) -> None:
        self.rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq/")
        self.aggregation_queue = os.getenv("AGGREGATION_QUEUE", "aggregation_tasks")
        self.results_queue = os.getenv("AGGREGATION_RESULTS_QUEUE", "aggregation_results")
        self.states: dict[str, AggregationState] = {}

    def _merge_results(self, state: AggregationState) -> dict[str, Any]:
        merged = {"ai_legal": {}, "ai_econom": {}, "sb_ai": {}, "contract_extractor": {}}
        merged.update(state.results)
        return merged

    async def _publish_final(self, channel: aio_pika.Channel, task_id: str, state: AggregationState) -> None:
        if not state.reply_to:
            return
        queue = await channel.declare_queue(state.reply_to, durable=True)
        payload = {
            "task_id": task_id,
            "result": self._merge_results(state),
        }
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload, ensure_ascii=False).encode(),
                correlation_id=task_id,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=queue.name,
        )

    def _ensure_state(self, task_id: str, reply_to: str | None, expected: Optional[Set[str]] = None) -> AggregationState:
        state = self.states.get(task_id)
        if state:
            if reply_to:
                state.reply_to = reply_to
            if expected:
                state.expected.update(expected)
            return state
        new_state = AggregationState(expected=expected or set(), reply_to=reply_to)
        self.states[task_id] = new_state
        return new_state

    async def _handle_init(self, channel: aio_pika.Channel, message: aio_pika.IncomingMessage) -> None:
        async with message.process():
            payload = json.loads(message.body.decode())
            task_id = payload.get("task_id") or message.correlation_id
            if not task_id:
                return
            expected = set(payload.get("expected_services", []))
            reply_to = payload.get("reply_to") or message.reply_to
            self._ensure_state(task_id, reply_to, expected)

    async def _handle_result(self, channel: aio_pika.Channel, message: aio_pika.IncomingMessage) -> None:
        async with message.process():
            payload = json.loads(message.body.decode())
            task_id = message.correlation_id or payload.get("task_id")
            service = payload.get("service")
            if not task_id or not service:
                return

            state = self._ensure_state(task_id, payload.get("reply_to") or message.reply_to)
            state.results[service] = payload.get("payload", {})

            if service in state.expected:
                state.expected.remove(service)

            if not state.expected:
                await self._publish_final(channel, task_id, state)
                self.states.pop(task_id, None)

    async def run(self) -> None:
        connection = await aio_pika.connect_robust(self.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            init_queue = await channel.declare_queue(self.aggregation_queue, durable=True)
            result_queue = await channel.declare_queue(self.results_queue, durable=True)

            await init_queue.consume(lambda msg: self._handle_init(channel, msg))
            await result_queue.consume(lambda msg: self._handle_result(channel, msg))

            await asyncio.Future()


def main() -> None:
    aggregator = Aggregator()
    asyncio.run(aggregator.run())


if __name__ == "__main__":
    main()

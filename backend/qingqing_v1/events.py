"""In-process event bus for AgentRun SSE streaming."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class RunEventBus:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    async def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._subscribers[run_id].append(queue)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            listeners = self._subscribers.get(run_id, [])
            if queue in listeners:
                listeners.remove(queue)
            if not listeners and run_id in self._subscribers:
                del self._subscribers[run_id]

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        payload = {"run_id": run_id, **event}
        async with self._lock:
            listeners = list(self._subscribers.get(run_id, []))
        for queue in listeners:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass


event_bus = RunEventBus()

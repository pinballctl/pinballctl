"""In-process event bus for Pi-side event routing."""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from queue import Queue
from collections import deque
from typing import Any, Deque, Dict, List
from uuid import uuid4


@dataclass(frozen=True)
class EventEnvelope:
    id: str
    ts: float
    name: str
    source: str | None
    params: Dict[str, Any]


class EventBus:
    def __init__(self, history_size: int = 200) -> None:
        self._lock = Lock()
        self._subscribers: List[Queue] = []
        self._history: Deque[EventEnvelope] = deque(maxlen=history_size)

    def emit(self, name: str, source: str | None = None, params: Dict[str, Any] | None = None) -> EventEnvelope:
        envelope = EventEnvelope(
            id=uuid4().hex,
            ts=time.time(),
            name=name,
            source=source,
            params=params or {},
        )
        with self._lock:
            self._history.append(envelope)
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(envelope)
            except Exception:
                continue
        return envelope

    def subscribe(self) -> Queue:
        q: Queue = Queue()
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass


_BUS: EventBus | None = None


def get_bus() -> EventBus:
    global _BUS
    if _BUS is None:
        _BUS = EventBus()
    return _BUS

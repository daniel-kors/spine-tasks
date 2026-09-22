"""Programmable security-event sinks, including JSONL through structlog."""

from pathlib import Path
from typing import Protocol

import structlog

from .models import SecurityEvent


class AuditSink(Protocol):
    def record(self, event: SecurityEvent) -> None: ...


class InMemoryAuditSink:
    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    def record(self, event: SecurityEvent) -> None:
        self.events.append(event)


class JsonlAuditSink:
    def __init__(self, path: Path) -> None:
        self.path = path

    def record(self, event: SecurityEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = event.model_dump(mode="json", exclude={"event_type"})
        with self.path.open("a", encoding="utf-8") as stream:
            logger = structlog.wrap_logger(
                structlog.PrintLogger(file=stream),
                processors=[structlog.processors.JSONRenderer(ensure_ascii=False)],
            )
            logger.warning(event.event_type, **payload)

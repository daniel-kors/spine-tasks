"""Structured JSON logging configuration."""

import logging
import sys
from typing import Any

import structlog


def configure_json_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO, force=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger() -> Any:
    return structlog.get_logger("ingestion")


class ListLogger:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events

    def info(self, event: str, **values: Any) -> None:
        self.events.append({"event": event, **values})


def make_list_logger(events: list[dict[str, Any]]) -> ListLogger:
    return ListLogger(events)

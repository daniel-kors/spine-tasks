"""Prepared FastAPI application with injected deterministic services."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from qa_api.application import create_app
from qa_api.dependencies import get_ask_service
from qa_api.fakes import FixtureGateway, StrictAnswerValidator
from qa_api.models import (
    Claim,
    ContextReference,
    DraftAnswer,
    RetrievedChunk,
)
from qa_api.service import AskQuestion
from qa_api.settings import Settings


class RecordingLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def info(self, event: str, **values: Any) -> None:
        self.events.append((event, values))

    def warning(self, event: str, **values: Any) -> None:
        self.events.append((event, values))

    def error(self, event: str, **values: Any) -> None:
        self.events.append((event, values))


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 22, 10, 0, tzinfo=UTC)


class FakeComposer:
    def __init__(self) -> None:
        self.calls = 0

    async def compose(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> DraftAnswer:
        del question
        self.calls += 1
        return DraftAnswer(
            claims=tuple(
                Claim(text=chunk.text, citation_ids=(chunk.reference.chunk_id,))
                for chunk in chunks
            ),
            summary=" ".join(chunk.text for chunk in chunks),
        )


class PreparedApplication:
    def __init__(
        self,
        app: FastAPI,
        service: AskQuestion,
        composer: FakeComposer,
        logger: RecordingLogger,
    ) -> None:
        self.app = app
        self.service = service
        self.composer = composer
        self.logger = logger


ServiceFactory = Callable[..., PreparedApplication]


@pytest.fixture
def known_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        workspace_id="alpha",
        required_scope="all-employees",
        text="Суточные составляют 1200 рублей.",
        reference=ContextReference(
            source_id="travel-policy",
            revision_id=UUID("11111111-1111-4111-8111-222222222222"),
            chunk_id="travel-v2-daily",
            locator={"heading": "Суточные", "paragraph": 1},
        ),
    )


@pytest.fixture
def service_factory(known_chunk: RetrievedChunk) -> ServiceFactory:
    def make(
        *,
        composer: Any | None = None,
        timeout: float = 1.0,
    ) -> PreparedApplication:
        logger = RecordingLogger()
        selected_composer = composer or FakeComposer()
        service = AskQuestion(
            FixtureGateway({"Какой размер суточных?": (known_chunk,)}),
            selected_composer,
            StrictAnswerValidator(),
            FixedClock(),
            logger,
            composer_timeout_seconds=timeout,
        )
        app = create_app(settings=Settings(qa_mode="fake"))
        app.state.logger = logger
        app.dependency_overrides[get_ask_service] = lambda: service
        return PreparedApplication(app, service, selected_composer, logger)

    return make


@pytest.fixture
async def client(service_factory: ServiceFactory) -> AsyncIterator[httpx.AsyncClient]:
    prepared = service_factory()
    transport = httpx.ASGITransport(app=prepared.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


def valid_request(**updates: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "workspace_id": "alpha",
        "user_id": "u-1",
        "scopes": ["all-employees"],
        "question": "Какой размер суточных?",
        "request_id": "r-1",
    }
    body.update(updates)
    return body

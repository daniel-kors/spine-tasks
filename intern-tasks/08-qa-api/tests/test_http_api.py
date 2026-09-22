"""Required in-memory HTTP checks for the Q&A API."""

import asyncio

import httpx
import pytest

from qa_api.models import DraftAnswer, RetrievedChunk

from .conftest import ServiceFactory, valid_request


@pytest.mark.asyncio
async def test_ask_returns_citation_with_exact_locator(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/ask", json=valid_request())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["citations"][0]["source_id"] == "travel-policy"
    assert body["citations"][0]["locator"] == {
        "heading": "Суточные",
        "paragraph": 1,
    }


@pytest.mark.asyncio
async def test_unknown_field_returns_422(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/ask",
        json=valid_request(unexpected="value"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["", "   "])
async def test_empty_question_returns_422(
    client: httpx.AsyncClient,
    question: str,
) -> None:
    response = await client.post(
        "/api/v1/ask",
        json=valid_request(question=question),
    )

    assert response.status_code == 422
    assert response.json()["retryable"] is False


@pytest.mark.asyncio
async def test_repeated_request_id_returns_same_logical_response(
    service_factory: ServiceFactory,
) -> None:
    prepared = service_factory()
    transport = httpx.ASGITransport(app=prepared.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.post("/api/v1/ask", json=valid_request())
        second = await client.post("/api/v1/ask", json=valid_request())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert prepared.composer.calls == 1


@pytest.mark.asyncio
async def test_other_workspace_does_not_receive_alpha_data(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/v1/ask",
        json=valid_request(workspace_id="beta"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "abstained"
    assert body["answer"] is None
    assert body["citations"] == []
    assert body["reasons"] == ["NO_CONTEXT"]


@pytest.mark.asyncio
async def test_composer_timeout_returns_controlled_503(
    service_factory: ServiceFactory,
) -> None:
    class SlowComposer:
        async def compose(
            self, question: str, chunks: tuple[RetrievedChunk, ...]
        ) -> DraftAnswer:
            del question, chunks
            await asyncio.sleep(1)
            raise AssertionError("unreachable")

    prepared = service_factory(composer=SlowComposer(), timeout=0.001)
    transport = httpx.ASGITransport(app=prepared.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/ask", json=valid_request())

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "COMPOSER_TIMEOUT"
    assert body["retryable"] is True
    assert set(body) == {"code", "message", "trace_id", "retryable"}


@pytest.mark.asyncio
async def test_trace_id_is_returned_and_logged(service_factory: ServiceFactory) -> None:
    prepared = service_factory()
    transport = httpx.ASGITransport(app=prepared.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/ask", json=valid_request())

    trace_id = response.json()["trace_id"]
    trace_events = [
        values
        for event, values in prepared.logger.events
        if event in {"ask_started", "ask_completed"}
    ]
    assert len(trace_events) == 2
    assert all(values["trace_id"] == trace_id for values in trace_events)


@pytest.mark.asyncio
async def test_health_endpoints_are_ready_without_language_model(
    client: httpx.AsyncClient,
) -> None:
    live = await client.get("/health/live")
    ready = await client.get("/health/ready")

    assert live.json() == {"status": "ok"}
    assert ready.json() == {"status": "ready", "mode": "fake"}

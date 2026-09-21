"""Contract tests shared by configured retriever implementations."""

import inspect

import pytest
from pydantic import ValidationError

from context_retriever import demo
from context_retriever.contracts import Retriever
from context_retriever.fake_retriever import FakeRetriever
from context_retriever.models import RetrievalQuery, RetrievalResult

from .factories import make_query, result_with, security_chunk, travel_chunk


@pytest.mark.asyncio
async def test_configured_question_returns_chunk() -> None:
    expected = result_with(travel_chunk())
    retriever = FakeRetriever({"Какой размер суточных?": expected})

    actual = await retriever.retrieve(make_query("Какой размер суточных?"))

    assert actual == expected
    assert retriever.received_queries[0].workspace_id == "alpha"


@pytest.mark.asyncio
async def test_unknown_question_returns_empty_result() -> None:
    retriever = FakeRetriever({"Известный вопрос": result_with(security_chunk())})

    actual = await retriever.retrieve(make_query("Неизвестный вопрос"))

    assert actual == RetrievalResult(
        chunks=(), strategy="configured-fake", index_version="fake-v1"
    )


@pytest.mark.asyncio
async def test_configured_error_is_raised_and_query_is_recorded() -> None:
    expected_error = RuntimeError("provider unavailable")
    query = make_query("Ошибка")
    retriever = FakeRetriever({}, {query.text: expected_error})

    with pytest.raises(RuntimeError, match="provider unavailable") as error:
        await retriever.retrieve(query)

    assert error.value is expected_error
    assert retriever.received_queries == [query]


def test_each_chunk_has_workspace_and_source_reference() -> None:
    result = result_with(travel_chunk(), security_chunk())

    for chunk in result.chunks:
        assert chunk.workspace_id == "alpha"
        assert chunk.reference.source_id
        assert chunk.reference.revision_id
        assert chunk.reference.chunk_id
        assert chunk.reference.locator


def test_empty_question_and_unknown_field_are_rejected() -> None:
    with pytest.raises(ValidationError):
        make_query("")

    with pytest.raises(ValidationError):
        RetrievalQuery(
            workspace_id="alpha",
            user_id="user-1",
            scopes=frozenset(),
            text="Вопрос",
            unexpected="value",
        )


def test_result_models_are_frozen() -> None:
    chunk = travel_chunk()
    result = result_with(chunk)

    with pytest.raises(ValidationError):
        chunk.text = "Изменённый текст"
    with pytest.raises(ValidationError):
        result.strategy = "changed"


def test_application_uses_retriever_contract_without_cognee_import() -> None:
    signature = inspect.signature(demo.show_answer)
    source = inspect.getsource(demo)

    assert signature.parameters["retriever"].annotation is Retriever
    assert "import cognee" not in source.lower()

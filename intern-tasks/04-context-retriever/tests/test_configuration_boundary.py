"""Tests for loading prepared fake results and running the demo boundary."""

from pathlib import Path

import pytest

from context_retriever.configuration import (
    ContextProviderUnavailableError,
    load_fake_configuration,
)
from context_retriever.demo import show_answer
from context_retriever.fake_retriever import FakeRetriever

from .factories import make_query

CONFIG_PATH = Path("data/fixtures/retriever/fake-results.json")


def configured_retriever() -> FakeRetriever:
    configuration = load_fake_configuration(CONFIG_PATH)
    return FakeRetriever(configuration.answers, configuration.errors)


@pytest.mark.asyncio
async def test_prepared_file_configures_two_answers() -> None:
    retriever = configured_retriever()

    travel = await retriever.retrieve(make_query("Какой размер суточных?"))
    security = await retriever.retrieve(make_query("Куда отправить подозрительное письмо?"))

    assert travel.chunks[0].reference.source_id == "travel-policy"
    assert security.chunks[0].reference.source_id == "security-policy"
    assert travel.index_version == security.index_version == "fake-v1"


@pytest.mark.asyncio
async def test_prepared_file_configures_provider_error() -> None:
    retriever = configured_retriever()

    with pytest.raises(ContextProviderUnavailableError) as error:
        await retriever.retrieve(make_query("Проверка недоступности Cognee"))

    assert error.value.error_code == "CONTEXT_PROVIDER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_demo_prints_prepared_source_and_text(capsys: pytest.CaptureFixture[str]) -> None:
    retriever = configured_retriever()

    await show_answer(retriever, "Какой размер суточных?")

    output = capsys.readouterr().out
    assert "Найдено фрагментов: 1" in output
    assert "Источник: travel-policy" in output
    assert "1200 рублей в день" in output

"""Run the configured fake retriever without Cognee or network access."""

import asyncio
from argparse import ArgumentParser
from pathlib import Path

from .configuration import ContextProviderUnavailableError, load_fake_configuration
from .contracts import Retriever
from .fake_retriever import FakeRetriever
from .models import RetrievalQuery

CONFIG_PATH = Path("data/fixtures/retriever/fake-results.json")


async def show_answer(retriever: Retriever, question: str) -> None:
    query = RetrievalQuery(
        workspace_id="alpha",
        user_id="demo-user",
        scopes=frozenset({"all-employees"}),
        text=question,
    )
    result = await retriever.retrieve(query)
    print(f"Найдено фрагментов: {len(result.chunks)}")
    for chunk in result.chunks:
        print(f"Источник: {chunk.reference.source_id}")
        print(f"Редакция: {chunk.reference.revision_id}")
        print(f"Текст: {chunk.text}")


def main() -> None:
    parser = ArgumentParser(description="Demonstrate the configured fake retriever")
    parser.add_argument("--question", default="Какой размер суточных?")
    arguments = parser.parse_args()
    configuration = load_fake_configuration(CONFIG_PATH)
    retriever = FakeRetriever(configuration.answers, configuration.errors)
    try:
        asyncio.run(show_answer(retriever, arguments.question))
    except ContextProviderUnavailableError as exc:
        print(f"Ошибка получения контекста: {exc.error_code}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

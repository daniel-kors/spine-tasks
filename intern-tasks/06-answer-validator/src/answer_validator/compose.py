"""Answer-composer boundary and deterministic offline fake."""

from typing import Protocol

from .models import DraftAnswer, RetrievedChunk


class AnswerComposer(Protocol):
    async def compose(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> DraftAnswer: ...


class FakeAnswerComposer:
    def __init__(self, answers: dict[str, DraftAnswer]) -> None:
        self.answers = answers

    async def compose(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> DraftAnswer:
        del chunks
        try:
            return self.answers[question]
        except KeyError as exc:
            raise KeyError(f"No fake answer configured for question: {question}") from exc

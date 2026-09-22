"""Boundaries injected into the application service."""

from datetime import datetime
from typing import Protocol

from .models import DraftAnswer, RetrievalResult, RetrievedChunk, Subject, ValidatedAnswer


class KnowledgeGateway(Protocol):
    async def retrieve(self, subject: Subject, text: str) -> RetrievalResult: ...


class AnswerComposer(Protocol):
    async def compose(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> DraftAnswer: ...


class AnswerValidator(Protocol):
    def validate(
        self, draft: DraftAnswer, available: tuple[RetrievedChunk, ...]
    ) -> ValidatedAnswer: ...


class Clock(Protocol):
    def now(self) -> datetime: ...

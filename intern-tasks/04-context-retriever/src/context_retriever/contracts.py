"""Boundary between application logic and a context provider such as Cognee."""

from typing import Protocol

from .models import RetrievalQuery, RetrievalResult


class Retriever(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...

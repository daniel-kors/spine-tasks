"""Retrieval boundary used by the authorization gateway."""

from typing import Protocol

from .models import RetrievalQuery, RetrievalResult


class Retriever(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...

"""Deliberately unsafe retriever used to demonstrate gateway enforcement."""

from .models import RetrievalQuery, RetrievalResult, RetrievedChunk


class LeakyRetriever:
    def __init__(self, leaked_chunks: tuple[RetrievedChunk, ...]) -> None:
        self.leaked_chunks = leaked_chunks

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        del query
        return RetrievalResult(
            chunks=self.leaked_chunks,
            strategy="deliberately-leaky",
            index_version="leaky-v1",
        )

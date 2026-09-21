"""A configured retriever that performs no search or external I/O."""

from .models import RetrievalQuery, RetrievalResult


class FakeRetriever:
    def __init__(
        self,
        answers: dict[str, RetrievalResult],
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.answers = answers
        self.errors = errors or {}
        self.received_queries: list[RetrievalQuery] = []

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        self.received_queries.append(query)
        if query.text in self.errors:
            raise self.errors[query.text]
        return self.answers.get(
            query.text,
            RetrievalResult(
                chunks=(),
                strategy="configured-fake",
                index_version="fake-v1",
            ),
        )

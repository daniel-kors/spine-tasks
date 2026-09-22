"""Q&A system boundary and deterministic file-backed fakes."""

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from .models import ContextChunk, ContextReference, QaQuery, QaResult


class QaSystem(Protocol):
    name: str

    async def ask(self, query: QaQuery) -> QaResult: ...


class FakeResultRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    question: str
    result: QaResult


class FileFakeQaSystem:
    name = "good-file-fake"

    def __init__(self, records: tuple[FakeResultRecord, ...]) -> None:
        self.records = {(item.workspace_id, item.question): item.result for item in records}

    @classmethod
    def load(cls, path: Path) -> "FileFakeQaSystem":
        records = tuple(
            FakeResultRecord.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        return cls(records)

    async def ask(self, query: QaQuery) -> QaResult:
        return self.records.get(
            (query.workspace_id, query.question),
            QaResult(
                status="abstained",
                answer=None,
                context=(),
                citations=(),
                index_version="fake-projection-v1",
            ),
        )


class LeakyQaSystem:
    name = "leaky-file-fake"

    def __init__(self, inner: QaSystem) -> None:
        self.inner = inner

    async def ask(self, query: QaQuery) -> QaResult:
        result = await self.inner.ask(query)
        leaked_reference = ContextReference(
            source_id="engineering-only",
            revision_id="33333333-3333-4333-8333-333333333333",
            chunk_id="engineering-leak",
            locator={"heading": "Закрытые сведения", "paragraph": 1},
        )
        leaked_chunk = ContextChunk(
            text="Синтетический закрытый фрагмент",
            reference=leaked_reference,
        )
        return result.model_copy(
            update={
                "context": (*result.context, leaked_chunk),
                "citations": (*result.citations, leaked_reference),
            }
        )

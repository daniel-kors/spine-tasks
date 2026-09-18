"""Storage adapters for immutable source revisions."""

from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from .models import SourceRevision


class RevisionRepository(Protocol):
    def find_by_checksum(
        self, workspace_id: str, source_id: str, checksum: str
    ) -> SourceRevision | None: ...

    def save(self, revision: SourceRevision) -> None: ...

    def history(self, workspace_id: str, source_id: str) -> list[SourceRevision]: ...


class InMemoryRevisionRepository:
    def __init__(self) -> None:
        self._revisions: list[SourceRevision] = []

    def find_by_checksum(
        self, workspace_id: str, source_id: str, checksum: str
    ) -> SourceRevision | None:
        return next(
            (
                revision
                for revision in reversed(self._revisions)
                if revision.workspace_id == workspace_id
                and revision.source_id == source_id
                and revision.checksum_sha256 == checksum
                and not revision.is_tombstone
            ),
            None,
        )

    def save(self, revision: SourceRevision) -> None:
        self._revisions.append(revision)

    def history(self, workspace_id: str, source_id: str) -> list[SourceRevision]:
        return sorted(
            (
                revision
                for revision in self._revisions
                if revision.workspace_id == workspace_id and revision.source_id == source_id
            ),
            key=lambda revision: revision.observed_at,
        )


class JsonlRevisionRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _read_all(self) -> list[SourceRevision]:
        if not self.path.exists():
            return []
        revisions: list[SourceRevision] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    revisions.append(SourceRevision.model_validate_json(line))
                except ValidationError as exc:
                    raise ValueError(
                        f"Invalid revision in {self.path}, line {line_number}: {exc}"
                    ) from exc
        return revisions

    def find_by_checksum(
        self, workspace_id: str, source_id: str, checksum: str
    ) -> SourceRevision | None:
        return next(
            (
                revision
                for revision in reversed(self._read_all())
                if revision.workspace_id == workspace_id
                and revision.source_id == source_id
                and revision.checksum_sha256 == checksum
                and not revision.is_tombstone
            ),
            None,
        )

    def save(self, revision: SourceRevision) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(revision.model_dump_json() + "\n")

    def history(self, workspace_id: str, source_id: str) -> list[SourceRevision]:
        return sorted(
            (
                revision
                for revision in self._read_all()
                if revision.workspace_id == workspace_id and revision.source_id == source_id
            ),
            key=lambda revision: revision.observed_at,
        )

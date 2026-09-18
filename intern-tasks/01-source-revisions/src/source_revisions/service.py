"""Rules for registering and retiring document revisions."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .checksum import file_sha256
from .models import RegisterResult, SourceRevision
from .repository import RevisionRepository


class RevisionService:
    def __init__(self, repository: RevisionRepository) -> None:
        self.repository = repository

    def register_file(
        self, workspace_id: str, source_id: str, path: Path, media_type: str
    ) -> RegisterResult:
        path = Path(path)
        checksum = file_sha256(path)
        previous = self.repository.history(workspace_id, source_id)
        current = previous[-1] if previous else None

        if current is not None and not current.is_tombstone and current.checksum_sha256 == checksum:
            existing = self.repository.find_by_checksum(workspace_id, source_id, checksum)
            if existing is not None:
                return RegisterResult(status="unchanged", revision=existing)

        revision = SourceRevision(
            revision_id=uuid4(),
            workspace_id=workspace_id,
            source_id=source_id,
            checksum_sha256=checksum,
            media_type=media_type,
            original_path=str(path),
            observed_at=datetime.now(UTC),
        )
        self.repository.save(revision)
        return RegisterResult(status="created", revision=revision)

    def tombstone(self, workspace_id: str, source_id: str) -> RegisterResult:
        previous = self.repository.history(workspace_id, source_id)
        if not previous:
            raise ValueError(f"Source {source_id!r} does not exist in workspace {workspace_id!r}")
        current = previous[-1]
        if current.is_tombstone:
            return RegisterResult(status="unchanged", revision=current)

        revision = SourceRevision(
            revision_id=uuid4(),
            workspace_id=workspace_id,
            source_id=source_id,
            checksum_sha256=current.checksum_sha256,
            media_type=current.media_type,
            original_path=current.original_path,
            observed_at=datetime.now(UTC),
            is_tombstone=True,
        )
        self.repository.save(revision)
        return RegisterResult(status="created", revision=revision)

    def history(self, workspace_id: str, source_id: str) -> list[SourceRevision]:
        return self.repository.history(workspace_id, source_id)

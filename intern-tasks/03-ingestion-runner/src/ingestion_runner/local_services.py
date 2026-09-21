"""Small local adapters compatible with the contracts from tasks 01 and 02."""

import json
import re
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from .models import ChunkDescription, RevisionRegistration

PARAGRAPH_RE = re.compile(r"\S(?:.*?\S)?(?=(?:\r?\n[ \t]*\r?\n)|\Z)", re.DOTALL)


class StoredRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    source_id: str
    revision_id: UUID
    checksum_sha256: str


class JsonlRevisionService:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def register_file(
        self, workspace_id: str, source_id: str, path: Path
    ) -> RevisionRegistration:
        checksum = sha256(path.read_bytes()).hexdigest()
        revisions = self._read_all()
        existing = next(
            (
                revision
                for revision in reversed(revisions)
                if revision.workspace_id == workspace_id
                and revision.source_id == source_id
                and revision.checksum_sha256 == checksum
            ),
            None,
        )
        if existing is not None:
            return RevisionRegistration(status="unchanged", revision_id=existing.revision_id)

        revision = StoredRevision(
            workspace_id=workspace_id,
            source_id=source_id,
            revision_id=uuid4(),
            checksum_sha256=checksum,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(revision.model_dump_json() + "\n")
        return RevisionRegistration(status="created", revision_id=revision.revision_id)

    def _read_all(self) -> list[StoredRevision]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as stream:
            return [StoredRevision.model_validate_json(line) for line in stream]


class LocalDocumentParser:
    def __init__(self, max_chars: int = 600) -> None:
        self.max_chars = max_chars

    async def parse(
        self, path: Path, workspace_id: str, source_id: str, revision_id: UUID
    ) -> tuple[ChunkDescription, ...]:
        try:
            original = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("INVALID_UTF8") from exc
        if not original.strip():
            raise ValueError("EMPTY_DOCUMENT")

        chunks: list[ChunkDescription] = []
        for match in PARAGRAPH_RE.finditer(original):
            chunks.extend(
                self._split_paragraph(
                    original,
                    match.start(),
                    match.end(),
                    workspace_id,
                    source_id,
                    revision_id,
                    len(chunks),
                )
            )
        if not chunks:
            raise ValueError("EMPTY_DOCUMENT")
        return tuple(chunks)

    def _split_paragraph(
        self,
        original: str,
        start: int,
        end: int,
        workspace_id: str,
        source_id: str,
        revision_id: UUID,
        ordinal_offset: int,
    ) -> list[ChunkDescription]:
        result: list[ChunkDescription] = []
        cursor = start
        while cursor < end:
            limit = min(cursor + self.max_chars, end)
            if limit < end:
                split = original.rfind(" ", cursor, limit + 1)
                if split > cursor:
                    limit = split
                else:
                    next_space = original.find(" ", limit, end)
                    limit = end if next_space < 0 else next_space
            text = original[cursor:limit]
            ordinal = ordinal_offset + len(result)
            identity = f"{revision_id}\x00{ordinal}\x00{text}".encode()
            result.append(
                ChunkDescription(
                    chunk_id=sha256(identity).hexdigest(),
                    workspace_id=workspace_id,
                    source_id=source_id,
                    revision_id=revision_id,
                    ordinal=ordinal,
                    text=text,
                    char_start=cursor,
                    char_end=limit,
                )
            )
            cursor = limit
            while cursor < end and original[cursor].isspace():
                cursor += 1
        return result


def write_chunk_manifest(path: Path, chunks: tuple[ChunkDescription, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in chunks:
            stream.write(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False) + "\n")
    temporary.replace(path)

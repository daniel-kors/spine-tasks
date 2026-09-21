"""Fast tests for ingestion orchestration rules."""

import os
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from ingestion_runner.logging import make_list_logger
from ingestion_runner.models import (
    ChunkDescription,
    IngestCommand,
    IngestionReceipt,
    RevisionRegistration,
)
from ingestion_runner.runner import IngestionRunner, UnsafeSourcePathError, discover_documents


class MemoryIdempotencyStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], IngestionReceipt] = {}

    async def initialize(self) -> None:
        return None

    async def get(self, workspace_id: str, idempotency_key: str) -> IngestionReceipt | None:
        return self.values.get((workspace_id, idempotency_key))

    async def complete(
        self, workspace_id: str, idempotency_key: str, receipt: IngestionReceipt
    ) -> None:
        self.values[(workspace_id, idempotency_key)] = receipt


class FakeRevisionService:
    def __init__(self) -> None:
        self.revisions: dict[tuple[str, str, str], UUID] = {}
        self.calls = 0

    async def register_file(
        self, workspace_id: str, source_id: str, path: Path
    ) -> RevisionRegistration:
        self.calls += 1
        checksum = sha256(path.read_bytes()).hexdigest()
        key = (workspace_id, source_id, checksum)
        if key in self.revisions:
            return RevisionRegistration(status="unchanged", revision_id=self.revisions[key])
        revision_id = uuid4()
        self.revisions[key] = revision_id
        return RevisionRegistration(status="created", revision_id=revision_id)


class FakeParser:
    def __init__(self) -> None:
        self.calls = 0

    async def parse(
        self, path: Path, workspace_id: str, source_id: str, revision_id: UUID
    ) -> tuple[ChunkDescription, ...]:
        self.calls += 1
        text = path.read_text(encoding="utf-8")
        return (
            ChunkDescription(
                chunk_id=sha256(f"{revision_id}:0:{text}".encode()).hexdigest(),
                workspace_id=workspace_id,
                source_id=source_id,
                revision_id=revision_id,
                ordinal=0,
                text=text,
                char_start=0,
                char_end=len(text),
            ),
        )


class FailingParser(FakeParser):
    async def parse(
        self, path: Path, workspace_id: str, source_id: str, revision_id: UUID
    ) -> tuple[ChunkDescription, ...]:
        if path.name == "broken.md":
            self.calls += 1
            raise RuntimeError("artificial parser failure")
        return await super().parse(path, workspace_id, source_id, revision_id)


def make_runner(
    tmp_path: Path,
    parser: FakeParser | None = None,
) -> tuple[IngestionRunner, FakeRevisionService, FakeParser, list[dict]]:
    revision_service = FakeRevisionService()
    selected_parser = parser or FakeParser()
    events: list[dict] = []

    def write_manifest(path: Path, chunks: tuple[ChunkDescription, ...]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("manifest", encoding="utf-8")

    runner = IngestionRunner(
        revision_service=revision_service,
        parser=selected_parser,
        idempotency_store=MemoryIdempotencyStore(),
        manifest_directory=tmp_path / "manifests",
        report_directory=tmp_path / "reports",
        manifest_writer=write_manifest,
        logger=make_list_logger(events),
    )
    return runner, revision_service, selected_parser, events


def write_documents(directory: Path, names: tuple[str, ...]) -> None:
    directory.mkdir()
    for name in names:
        (directory / name).write_text(f"Содержимое {name}", encoding="utf-8")


@pytest.mark.asyncio
async def test_three_valid_files_create_three_receipt_items(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    write_documents(documents, ("c.txt", "a.md", "b.md"))
    runner, _, _, _ = make_runner(tmp_path)

    receipt = await runner.run(IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="three-valid"
    ))

    assert [item.source_id for item in receipt.items] == ["a", "b", "c"]
    assert [item.status for item in receipt.items] == ["indexed", "indexed", "indexed"]


@pytest.mark.asyncio
async def test_failure_does_not_hide_other_files_or_create_manifest_event(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    write_documents(documents, ("a.md", "broken.md", "c.txt"))
    runner, _, _, events = make_runner(tmp_path, FailingParser())

    receipt = await runner.run(
        IngestCommand(workspace_id="alpha", directory=documents, idempotency_key="failure"),
        continue_on_error=True,
    )

    assert [item.status for item in receipt.items] == ["indexed", "failed", "indexed"]
    assert receipt.items[1].error_code == "PROCESSING_ERROR"
    ready_sources = {
        event["source_id"] for event in events if event["event"] == "manifest_ready"
    }
    assert ready_sources == {"a", "c"}
    assert len(list((tmp_path / "manifests").glob("*.jsonl"))) == 2


@pytest.mark.asyncio
async def test_repeated_key_returns_same_run_without_processing_again(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    write_documents(documents, ("a.md",))
    runner, revisions, parser, _ = make_runner(tmp_path)
    command = IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="same-key"
    )

    first = await runner.run(command)
    second = await runner.run(command)

    assert second.run_id == first.run_id
    assert revisions.calls == 1
    assert parser.calls == 1


@pytest.mark.asyncio
async def test_new_key_and_unchanged_files_return_unchanged(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    write_documents(documents, ("a.md", "b.txt"))
    runner, _, _, _ = make_runner(tmp_path)

    await runner.run(IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="first-key"
    ))
    second = await runner.run(IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="second-key"
    ))

    assert [item.status for item in second.items] == ["unchanged", "unchanged"]


def test_symlink_or_traversal_escaping_directory_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("Закрытый документ", encoding="utf-8")
    link = documents / "link.md"
    try:
        os.symlink(outside, link)
    except OSError:
        monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter([outside]))

    with pytest.raises(UnsafeSourcePathError):
        discover_documents(documents)

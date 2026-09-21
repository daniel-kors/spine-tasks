"""Application service for deterministic, idempotent directory ingestion."""

import json
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol
from uuid import UUID, uuid4

from .idempotency import IdempotencyStore
from .models import (
    ChunkDescription,
    IngestCommand,
    IngestionReceipt,
    ItemReceipt,
    RevisionRegistration,
)


class RevisionService(Protocol):
    async def register_file(
        self, workspace_id: str, source_id: str, path: Path
    ) -> RevisionRegistration: ...


class DocumentParser(Protocol):
    async def parse(
        self, path: Path, workspace_id: str, source_id: str, revision_id: UUID
    ) -> tuple[ChunkDescription, ...]: ...


class EventLogger(Protocol):
    def info(self, event: str, **values: Any) -> Any: ...


ManifestWriter = Callable[[Path, tuple[ChunkDescription, ...]], None]


class UnsafeSourcePathError(ValueError):
    """A symbolic link escapes the requested input directory."""


class IngestionRunner:
    def __init__(
        self,
        revision_service: RevisionService,
        parser: DocumentParser,
        idempotency_store: IdempotencyStore,
        manifest_directory: Path,
        report_directory: Path,
        manifest_writer: ManifestWriter,
        logger: EventLogger,
    ) -> None:
        self.revision_service = revision_service
        self.parser = parser
        self.idempotency_store = idempotency_store
        self.manifest_directory = manifest_directory
        self.report_directory = report_directory
        self.manifest_writer = manifest_writer
        self.logger = logger

    async def run(
        self, command: IngestCommand, *, continue_on_error: bool = True
    ) -> IngestionReceipt:
        await self.idempotency_store.initialize()
        previous = await self.idempotency_store.get(
            command.workspace_id, command.idempotency_key
        )
        if previous is not None:
            self.logger.info(
                "ingestion_replayed",
                run_id=str(previous.run_id),
                workspace_id=command.workspace_id,
                stage="idempotency",
                status="unchanged",
                duration_ms=0,
            )
            return previous

        paths = discover_documents(command.directory)
        run_id = uuid4()
        items: list[ItemReceipt] = []
        self.logger.info(
            "ingestion_started",
            run_id=str(run_id),
            workspace_id=command.workspace_id,
            stage="discovery",
            status="started",
            duration_ms=0,
        )
        for path in paths:
            source_id = source_id_for(command.directory, path)
            started = perf_counter()
            try:
                registration = await self.revision_service.register_file(
                    command.workspace_id, source_id, path
                )
                chunks = await self.parser.parse(
                    path, command.workspace_id, source_id, registration.revision_id
                )
                manifest_path = self.manifest_directory / f"{registration.revision_id}.jsonl"
                self.manifest_writer(manifest_path, chunks)
                status = "indexed" if registration.status == "created" else "unchanged"
                item = ItemReceipt(
                    source_id=source_id,
                    status=status,
                    revision_id=registration.revision_id,
                    chunk_count=len(chunks),
                    error_code=None,
                )
                self.logger.info(
                    "manifest_ready",
                    run_id=str(run_id),
                    workspace_id=command.workspace_id,
                    source_id=source_id,
                    stage="manifest",
                    status=status,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
            except Exception as exc:
                item = ItemReceipt(
                    source_id=source_id,
                    status="failed",
                    revision_id=None,
                    chunk_count=0,
                    error_code=error_code_for(exc),
                )
                self.logger.info(
                    "ingestion_item_failed",
                    run_id=str(run_id),
                    workspace_id=command.workspace_id,
                    source_id=source_id,
                    stage="processing",
                    status="failed",
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                    error_code=item.error_code,
                )
            items.append(item)
            receipt = IngestionReceipt(
                run_id=run_id, workspace_id=command.workspace_id, items=tuple(items)
            )
            write_progress_report(self.report_directory / f"{run_id}.json", receipt)
            if item.status == "failed" and not continue_on_error:
                break

        receipt = IngestionReceipt(
            run_id=run_id, workspace_id=command.workspace_id, items=tuple(items)
        )
        await self.idempotency_store.complete(
            command.workspace_id, command.idempotency_key, receipt
        )
        return receipt


def discover_documents(directory: Path) -> tuple[Path, ...]:
    root = directory.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(directory)
    candidates: list[Path] = []
    for path in directory.rglob("*"):
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise UnsafeSourcePathError(f"Source path escapes input directory: {path.name}")
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            candidates.append(path)
    return tuple(sorted(candidates, key=lambda path: path.relative_to(directory).as_posix()))


def source_id_for(directory: Path, path: Path) -> str:
    return path.relative_to(directory).with_suffix("").as_posix()


def error_code_for(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IO_ERROR"
    value = str(exc)
    if value in {"INVALID_UTF8", "EMPTY_DOCUMENT"}:
        return value
    return "PROCESSING_ERROR"


def write_progress_report(path: Path, receipt: IngestionReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)

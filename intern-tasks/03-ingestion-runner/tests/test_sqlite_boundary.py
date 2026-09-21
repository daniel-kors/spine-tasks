"""Integration tests for SQLite idempotency and local file adapters."""

import sqlite3
from pathlib import Path

import pytest

from ingestion_runner.idempotency import SqliteIdempotencyStore
from ingestion_runner.local_services import (
    JsonlRevisionService,
    LocalDocumentParser,
    write_chunk_manifest,
)
from ingestion_runner.logging import make_list_logger
from ingestion_runner.models import IngestCommand
from ingestion_runner.runner import IngestionRunner


def build_runner(tmp_path: Path, events: list[dict]) -> IngestionRunner:
    return IngestionRunner(
        revision_service=JsonlRevisionService(tmp_path / "revisions.jsonl"),
        parser=LocalDocumentParser(),
        idempotency_store=SqliteIdempotencyStore(tmp_path / "runs.db"),
        manifest_directory=tmp_path / "manifests",
        report_directory=tmp_path / "reports",
        manifest_writer=write_chunk_manifest,
        logger=make_list_logger(events),
    )


@pytest.mark.asyncio
async def test_sqlite_returns_same_receipt_for_repeated_key(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "a.md").write_text("# Раздел\n\nТекст документа.", encoding="utf-8")
    events: list[dict] = []
    runner = build_runner(tmp_path, events)
    command = IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="sqlite-key"
    )

    first = await runner.run(command)
    second = await runner.run(command)

    assert second == first
    with sqlite3.connect(tmp_path / "runs.db") as database:
        command_count = database.execute("SELECT COUNT(*) FROM command_results").fetchone()[0]
        report_count = database.execute("SELECT COUNT(*) FROM run_reports").fetchone()[0]
    assert command_count == report_count == 1


@pytest.mark.asyncio
async def test_workspace_scopes_identical_idempotency_keys(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "a.txt").write_text("Текст", encoding="utf-8")
    runner = build_runner(tmp_path, [])

    alpha = await runner.run(IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="shared"
    ))
    beta = await runner.run(IngestCommand(
        workspace_id="beta", directory=documents, idempotency_key="shared"
    ))

    assert alpha.run_id != beta.run_id
    assert alpha.workspace_id == "alpha"
    assert beta.workspace_id == "beta"


@pytest.mark.asyncio
async def test_progress_report_and_manifests_contain_source_references(tmp_path: Path) -> None:
    documents = tmp_path / "documents"
    documents.mkdir()
    (documents / "a.md").write_text("# Раздел\n\nТекст.", encoding="utf-8")
    runner = build_runner(tmp_path, [])

    receipt = await runner.run(IngestCommand(
        workspace_id="alpha", directory=documents, idempotency_key="references"
    ))

    report = tmp_path / "reports" / f"{receipt.run_id}.json"
    manifest = next((tmp_path / "manifests").glob("*.jsonl"))
    assert '"workspace_id": "alpha"' in report.read_text(encoding="utf-8")
    manifest_text = manifest.read_text(encoding="utf-8")
    assert '"workspace_id": "alpha"' in manifest_text
    assert '"source_id": "a"' in manifest_text

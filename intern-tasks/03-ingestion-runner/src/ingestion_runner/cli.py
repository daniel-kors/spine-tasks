"""Typer command line interface for directory ingestion."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from .idempotency import SqliteIdempotencyStore
from .local_services import JsonlRevisionService, LocalDocumentParser, write_chunk_manifest
from .logging import configure_json_logging, get_logger
from .models import IngestCommand
from .runner import IngestionRunner, UnsafeSourcePathError

app = typer.Typer(help="Ingest a directory without duplicating command results.")


@app.callback()
def main() -> None:
    """Run ingestion commands."""


@app.command()
def ingest(
    directory: Annotated[Path, typer.Option(help="Directory containing Markdown/TXT")],
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    idempotency_key: Annotated[str, typer.Option(help="Stable command retry key")],
    continue_on_error: Annotated[
        bool, typer.Option("--continue-on-error/--stop-on-error", help="Error handling mode")
    ] = True,
    database: Annotated[Path, typer.Option(help="SQLite command store")] = Path("data/runs.db"),
    revisions: Annotated[Path, typer.Option(help="JSONL revision store")] = Path(
        "data/revisions.jsonl"
    ),
    manifests: Annotated[Path, typer.Option(help="Chunk manifest directory")] = Path(
        "data/manifests"
    ),
    reports: Annotated[Path, typer.Option(help="Progress report directory")] = Path(
        "data/reports"
    ),
) -> None:
    configure_json_logging()
    command = IngestCommand(
        workspace_id=workspace,
        directory=directory,
        idempotency_key=idempotency_key,
    )
    runner = IngestionRunner(
        revision_service=JsonlRevisionService(revisions),
        parser=LocalDocumentParser(),
        idempotency_store=SqliteIdempotencyStore(database),
        manifest_directory=manifests,
        report_directory=reports,
        manifest_writer=write_chunk_manifest,
        logger=get_logger(),
    )
    try:
        receipt = asyncio.run(runner.run(command, continue_on_error=continue_on_error))
    except (OSError, ValueError, UnsafeSourcePathError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(receipt.model_dump_json(indent=2))


if __name__ == "__main__":
    app()

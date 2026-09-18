"""Typer command line interface for the revision service."""

import json
from pathlib import Path
from typing import Annotated

import typer

from .repository import JsonlRevisionRepository
from .service import RevisionService

app = typer.Typer(help="Store immutable source revisions.")
DEFAULT_STORE = Path("data/revisions.jsonl")


def _service(store: Path) -> RevisionService:
    return RevisionService(JsonlRevisionRepository(store))


def _fail(exc: OSError | ValueError) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=1) from exc


@app.command()
def register(
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    source: Annotated[str, typer.Option(help="Stable source identifier")],
    file: Annotated[Path, typer.Option(help="Document to register")],
    media_type: Annotated[str, typer.Option(help="Document media type")] = "text/markdown",
    store: Annotated[Path, typer.Option(help="JSONL revision store")] = DEFAULT_STORE,
) -> None:
    try:
        result = _service(store).register_file(workspace, source, file, media_type)
    except (OSError, ValueError) as exc:
        _fail(exc)
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def history(
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    source: Annotated[str, typer.Option(help="Stable source identifier")],
    store: Annotated[Path, typer.Option(help="JSONL revision store")] = DEFAULT_STORE,
) -> None:
    try:
        revisions = _service(store).history(workspace, source)
    except (OSError, ValueError) as exc:
        _fail(exc)
    typer.echo(json.dumps([revision.model_dump(mode="json") for revision in revisions], indent=2))


@app.command()
def tombstone(
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    source: Annotated[str, typer.Option(help="Stable source identifier")],
    store: Annotated[Path, typer.Option(help="JSONL revision store")] = DEFAULT_STORE,
) -> None:
    try:
        result = _service(store).tombstone(workspace, source)
    except (OSError, ValueError) as exc:
        _fail(exc)
    typer.echo(result.model_dump_json(indent=2))


if __name__ == "__main__":
    app()

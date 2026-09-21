"""Command line interface for parsing and verifying documents."""

from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from .manifest import ManifestError, verify_manifest, write_manifest
from .markdown_parser import MarkdownParser
from .models import SourceDocument
from .parser import DocumentParseError

app = typer.Typer(help="Create stable chunks with exact source locators.")


def _fail(exc: OSError | ValueError | DocumentParseError | ManifestError) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=1) from exc


@app.command("parse")
def parse_document(
    file: Annotated[Path, typer.Option(help="UTF-8 Markdown or TXT source")],
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    source: Annotated[str, typer.Option(help="Stable source identifier")],
    revision: Annotated[UUID, typer.Option(help="Source revision UUID")],
    media_type: Annotated[str, typer.Option(help="text/markdown or text/plain")] = "text/markdown",
    max_chars: Annotated[int, typer.Option(min=1, help="Maximum chunk length")] = 600,
    output: Annotated[Path | None, typer.Option(help="Output JSONL path")] = None,
) -> None:
    manifest_path = output or Path("data/manifests") / f"{revision}.jsonl"
    document = SourceDocument(
        workspace_id=workspace,
        source_id=source,
        revision_id=revision,
        path=file,
        media_type=media_type,
    )
    try:
        chunks = MarkdownParser(max_chars=max_chars).parse(document)
        write_manifest(manifest_path, chunks)
    except (OSError, ValueError, DocumentParseError, ManifestError) as exc:
        _fail(exc)
    typer.echo(f"Created {len(chunks)} chunks in {manifest_path}")


@app.command("verify-manifest")
def verify_manifest_command(
    file: Annotated[Path, typer.Option(help="Original UTF-8 source")],
    manifest: Annotated[Path, typer.Option(help="JSONL manifest to verify")],
) -> None:
    try:
        count = verify_manifest(file, manifest)
    except (OSError, ValueError, DocumentParseError, ManifestError) as exc:
        _fail(exc)
    typer.echo(f"Verified {count} chunks")


if __name__ == "__main__":
    app()

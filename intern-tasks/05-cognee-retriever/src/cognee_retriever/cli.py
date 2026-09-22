"""Commands for building, activating, rebuilding, and querying projections."""

import asyncio
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer

from .cognee_client import CogneeClient, ConfiguredFakeCogneeClient, RealCogneeClient
from .cognee_retriever import CogneeRetriever
from .manual_check import run_manual_checks
from .models import RetrievalQuery
from .projections import ProjectionBuilder, ProjectionStore
from .settings import Settings

app = typer.Typer(help="Manage rebuildable Cognee projections.")


@app.callback()
def main() -> None:
    """Manage projection versions and retrieve context."""


def make_client(settings: Settings, project_root: Path) -> CogneeClient:
    if settings.cognee_provider == "real":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required when COGNEE_PROVIDER=real")
        return RealCogneeClient(project_root)
    return ConfiguredFakeCogneeClient(
        settings.fake_dataset_directory, settings.fake_results_path
    )


async def build_projection(workspace: str, manifests: Path, activate: bool) -> str:
    settings = Settings()
    store = ProjectionStore(settings.projection_database)
    client = make_client(settings, Path.cwd())
    projection = await ProjectionBuilder(client, store).build(
        workspace, manifests, activate=activate
    )
    return projection.model_dump_json(indent=2)


@app.command("build-index")
def build_index(
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    manifests: Annotated[Path, typer.Option(help="Source chunk manifests")] = Path(
        "data/fixtures/manifests"
    ),
    activate: Annotated[bool, typer.Option("--activate/--no-activate")] = True,
) -> None:
    try:
        typer.echo(asyncio.run(build_projection(workspace, manifests, activate)))
    except Exception as exc:
        typer.echo(f"Error: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def rebuild(
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    manifests: Annotated[Path, typer.Option(help="Source chunk manifests")] = Path(
        "data/fixtures/manifests"
    ),
) -> None:
    try:
        typer.echo(asyncio.run(build_projection(workspace, manifests, True)))
    except Exception as exc:
        typer.echo(f"Error: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("activate-index")
def activate_index(
    projection_id: Annotated[UUID, typer.Option(help="Ready projection UUID")],
) -> None:
    async def activate() -> str:
        settings = Settings()
        store = ProjectionStore(settings.projection_database)
        await store.initialize()
        projection = await store.activate(projection_id)
        return projection.model_dump_json(indent=2)

    try:
        typer.echo(asyncio.run(activate()))
    except Exception as exc:
        typer.echo(f"Error: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("retrieve-context")
def retrieve_context(
    workspace: Annotated[str, typer.Option(help="Workspace identifier")],
    user: Annotated[str, typer.Option(help="User identifier")],
    question: Annotated[str, typer.Option(help="Question text")],
    scopes: Annotated[str, typer.Option(help="Comma-separated access scopes")],
) -> None:
    async def retrieve() -> str:
        settings = Settings()
        store = ProjectionStore(settings.projection_database)
        client = make_client(settings, Path.cwd())
        result = await CogneeRetriever(client, store).retrieve(
            RetrievalQuery(
                workspace_id=workspace,
                user_id=user,
                scopes=frozenset(value.strip() for value in scopes.split(",") if value.strip()),
                text=question,
            )
        )
        return result.model_dump_json(indent=2)

    try:
        typer.echo(asyncio.run(retrieve()))
    except Exception as exc:
        typer.echo(f"Error: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("manual-check")
def manual_check(
    cases: Annotated[Path, typer.Option(help="Prepared JSONL questions")] = Path(
        "data/fixtures/questions/manual-check.jsonl"
    ),
    output: Annotated[Path, typer.Option(help="Metrics-only JSONL output")] = Path(
        "build/manual-check-results.jsonl"
    ),
    user: Annotated[str, typer.Option(help="User identifier")] = "manual-check-user",
) -> None:
    async def execute() -> int:
        settings = Settings()
        retriever = CogneeRetriever(
            make_client(settings, Path.cwd()), ProjectionStore(settings.projection_database)
        )
        results = await run_manual_checks(retriever, cases, output, user_id=user)
        return len(results)

    try:
        count = asyncio.run(execute())
        typer.echo(f"Saved {count} metric records to {output}")
    except Exception as exc:
        typer.echo(f"Error: {type(exc).__name__}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()

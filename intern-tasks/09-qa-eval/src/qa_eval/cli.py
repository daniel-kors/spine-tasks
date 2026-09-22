"""Typer command for running the complete evaluation."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .dataset import load_eval_cases
from .reports import write_reports
from .runner import EvaluationRunner
from .system import FileFakeQaSystem, LeakyQaSystem

app = typer.Typer(no_args_is_help=True)


@app.callback()
def root() -> None:
    """Run reproducible quality checks for a Q&A adapter."""


@app.command("run")
def run_evaluation(
    dataset: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output")] = Path("build"),
    adapter: Annotated[str, typer.Option("--adapter")] = "good-fake",
    fake_results: Annotated[
        Path,
        typer.Option("--fake-results", exists=True, dir_okay=False, readable=True),
    ] = Path("data/fixtures/good-results.jsonl"),
) -> None:
    """Validate the full dataset, run the adapter, and write both reports."""
    try:
        cases = load_eval_cases(dataset)
        base = FileFakeQaSystem.load(fake_results)
        if adapter == "good-fake":
            system = base
        elif adapter == "leaky-fake":
            system = LeakyQaSystem(base)
        else:
            raise ValueError(f"Unknown adapter: {adapter}")
        report = asyncio.run(EvaluationRunner(system).run(cases))
        json_path, markdown_path = write_reports(report, output)
    except (OSError, ValueError) as exc:
        typer.echo(f"INPUT_ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    table = Table(title="Q&A readiness")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Cases", str(report.metrics.total_cases))
    table.add_row("Forbidden sources", str(report.metrics.forbidden_source_count))
    table.add_row("Citation validity", f"{report.metrics.citation_validity_rate:.1%}")
    table.add_row("Expected sources", f"{report.metrics.expected_source_rate:.1%}")
    table.add_row("Status accuracy", f"{report.metrics.status_accuracy:.1%}")
    table.add_row("Ready", "yes" if report.ready else "no")
    Console().print(table)
    typer.echo(f"JSON report: {json_path}")
    typer.echo(f"Markdown report: {markdown_path}")
    if not report.ready:
        raise typer.Exit(code=1)


def main() -> None:
    app()

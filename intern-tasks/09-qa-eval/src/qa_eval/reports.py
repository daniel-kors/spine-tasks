"""Write machine-readable JSON and a concise Markdown failure table."""

from pathlib import Path

from .models import EvaluationReport


def write_reports(report: EvaluationReport, output_directory: Path) -> tuple[Path, Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / "report.json"
    markdown_path = output_directory / "report.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def render_markdown(report: EvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# Q&A evaluation report",
        "",
        f"- Dataset version: `{report.dataset_version}`",
        f"- Adapter: `{report.adapter_name}`",
        f"- Projection versions: `{', '.join(report.projection_versions)}`",
        f"- Run at: `{report.run_at.isoformat()}`",
        f"- Ready: `{'yes' if report.ready else 'no'}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Total cases | {metrics.total_cases} |",
        f"| Forbidden sources | {metrics.forbidden_source_count} |",
        f"| Citation validity | {metrics.citation_validity_rate:.1%} |",
        f"| Expected sources | {metrics.expected_source_rate:.1%} |",
        f"| Status accuracy | {metrics.status_accuracy:.1%} |",
        f"| Required content | {metrics.required_content_rate:.1%} |",
        f"| Average duration | {metrics.average_duration_ms:.2f} ms |",
        "",
        "## Failures",
        "",
        "| Case | Code | Expected | Actual |",
        "| --- | --- | --- | --- |",
    ]
    if report.failures:
        lines.extend(
            f"| {_cell(item.case_id)} | {_cell(item.code)} | "
            f"{_cell(item.expected)} | {_cell(item.actual)} |"
            for item in report.failures
        )
    else:
        lines.append("| — | — | — | — |")
    return "\n".join(lines) + "\n"


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")

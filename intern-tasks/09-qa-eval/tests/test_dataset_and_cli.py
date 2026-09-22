"""Dataset validation, reproducible fake, and command exit codes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qa_eval.cli import app
from qa_eval.dataset import load_eval_cases
from qa_eval.models import QaQuery
from qa_eval.system import FileFakeQaSystem

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "evals" / "v1.jsonl"
FAKE_RESULTS = ROOT / "data" / "fixtures" / "good-results.jsonl"


def test_empty_dataset_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        load_eval_cases(path)


def test_duplicate_case_id_is_rejected(tmp_path: Path) -> None:
    record = {
        "schema_version": "1.0",
        "case_id": "duplicate",
        "workspace_id": "alpha",
        "scopes": ["all-employees"],
        "question": "Вопрос",
        "expected_status": "abstained",
        "expected_source_ids": [],
        "required_facts": [],
        "forbidden_source_ids": [],
    }
    line = json.dumps(record, ensure_ascii=False)
    path = tmp_path / "duplicate.jsonl"
    path.write_text(f"{line}\n{line}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate case_id"):
        load_eval_cases(path)


@pytest.mark.asyncio
async def test_file_fake_is_reproducible() -> None:
    system = FileFakeQaSystem.load(FAKE_RESULTS)
    case = load_eval_cases(DATASET)[0]
    query = QaQuery(
        workspace_id=case.workspace_id,
        scopes=case.scopes,
        question=case.question,
    )

    first = await system.ask(query)
    second = await system.ask(query)

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_good_fake_cli_writes_reports_and_returns_zero(tmp_path: Path) -> None:
    output = tmp_path / "good"
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(DATASET),
            "--fake-results",
            str(FAKE_RESULTS),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads((output / "report.json").read_text(encoding="utf-8"))["ready"] is True
    assert (output / "report.md").exists()


def test_leaky_fake_cli_returns_one(tmp_path: Path) -> None:
    output = tmp_path / "leaky"
    result = CliRunner().invoke(
        app,
        [
            "run",
            str(DATASET),
            "--fake-results",
            str(FAKE_RESULTS),
            "--adapter",
            "leaky-fake",
            "--output",
            str(output),
        ],
    )

    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert result.exit_code == 1
    assert report["ready"] is False
    assert report["metrics"]["forbidden_source_count"] > 0

"""Tests for the JSONL manifest boundary and command line interface."""

import json
from pathlib import Path

from typer.testing import CliRunner

from document_chunks.cli import app
from document_chunks.manifest import read_manifest, verify_manifest, write_manifest
from document_chunks.markdown_parser import MarkdownParser
from document_chunks.models import SourceDocument

REVISION = "11111111-1111-4111-8111-222222222222"
runner = CliRunner()


def test_manifest_round_trip_and_verification(tmp_path: Path) -> None:
    source = tmp_path / "policy.md"
    source.write_text("# Правила\n\nТочный текст источника.", encoding="utf-8")
    document = SourceDocument(
        workspace_id="alpha",
        source_id="policy",
        revision_id=REVISION,
        path=source,
        media_type="text/markdown",
    )
    chunks = MarkdownParser().parse(document)
    manifest = tmp_path / "manifest.jsonl"

    write_manifest(manifest, chunks)

    assert read_manifest(manifest) == chunks
    assert verify_manifest(source, manifest) == len(chunks)
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == len(chunks)


def test_verify_command_fails_after_locator_is_changed(tmp_path: Path) -> None:
    source = tmp_path / "policy.md"
    source.write_text("# Правила\n\nТочный текст источника.", encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    parse_result = runner.invoke(
        app,
        [
            "parse",
            "--workspace",
            "alpha",
            "--source",
            "policy",
            "--revision",
            REVISION,
            "--file",
            str(source),
            "--output",
            str(manifest),
        ],
    )
    assert parse_result.exit_code == 0

    lines = manifest.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["locator"]["char_start"] += 1
    lines[0] = json.dumps(first, ensure_ascii=False)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verify_result = runner.invoke(
        app,
        ["verify-manifest", "--file", str(source), "--manifest", str(manifest)],
    )

    assert verify_result.exit_code == 1
    assert "Locator mismatch at manifest line 1" in verify_result.output

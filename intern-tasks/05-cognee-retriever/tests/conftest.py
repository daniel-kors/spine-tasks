"""Shared fixtures for the Cognee retriever test suite."""

import json
from pathlib import Path
from uuid import UUID

import pytest


@pytest.fixture
def revision_id() -> UUID:
    return UUID("11111111-1111-4111-8111-111111111111")


@pytest.fixture
def manifest_directory(tmp_path: Path, revision_id: UUID) -> Path:
    directory = tmp_path / "manifests"
    directory.mkdir()
    records = [
        {
            "workspace_id": "alpha",
            "required_scope": "all-employees",
            "text": "Суточные составляют 1200 рублей.",
            "reference": {
                "source_id": "travel-policy",
                "revision_id": str(revision_id),
                "chunk_id": "travel-policy:0",
                "locator": {"path": "travel-policy.md", "start_line": 1, "end_line": 1},
            },
        },
        {
            "workspace_id": "alpha",
            "required_scope": "engineering",
            "text": "Кодовое имя прототипа — Маяк.",
            "reference": {
                "source_id": "engineering-only",
                "revision_id": str(revision_id),
                "chunk_id": "engineering-only:0",
                "locator": {"path": "engineering-only.md", "start_line": 1, "end_line": 1},
            },
        },
    ]
    target = directory / "alpha.jsonl"
    target.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return directory

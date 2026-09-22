"""Idempotency and deterministic-workflow architecture checks."""

import ast
from pathlib import Path

import pytest

from temporal_reindex.activities import ReindexActivities
from temporal_reindex.models import IndexBatchInput, ProjectionInput
from temporal_reindex.service import InMemoryProjectionService
from temporal_reindex.workflow import make_batch_descriptors

from .helpers import reindex_input


def test_twenty_five_items_are_split_into_ten_ten_five() -> None:
    batches = make_batch_descriptors(reindex_input(), "workflow-1")

    assert [len(batch.manifest_paths) for batch in batches] == [10, 10, 5]
    assert [batch.idempotency_key for batch in batches] == [
        "workflow-1/index-batch-0/0",
        "workflow-1/index-batch-1/1",
        "workflow-1/index-batch-2/2",
    ]


@pytest.mark.asyncio
async def test_repeated_activity_does_not_duplicate_indexed_items() -> None:
    service = InMemoryProjectionService()
    activities = ReindexActivities(service)
    projection = ProjectionInput(
        workspace_id="alpha",
        projection_id="projection-1",
        expected_count=2,
    )
    batch = IndexBatchInput(
        workspace_id="alpha",
        projection_id="projection-1",
        manifest_paths=("one.jsonl", "two.jsonl"),
        batch_number=0,
        idempotency_key="workflow-1/index-batch-0/0",
    )
    await service.create(projection)

    first = await activities.index_batch(batch)
    second = await activities.index_batch(batch)

    state = service.projections[("alpha", "projection-1")]
    assert first == second == 2
    assert state.indexed_by_key == {batch.idempotency_key: 2}


def test_workflow_source_contains_no_direct_io_or_nondeterminism() -> None:
    path = Path(__file__).parents[1] / "src" / "temporal_reindex" / "workflow.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_imports = {"os", "pathlib", "random", "secrets", "socket", "time", "uuid"}
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert imported.isdisjoint(forbidden_imports)
    assert called_names.isdisjoint({"open", "input"})

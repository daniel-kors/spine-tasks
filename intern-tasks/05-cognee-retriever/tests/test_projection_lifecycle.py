"""Projection lifecycle, rebuilding, and source immutability checks."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from cognee_retriever.cognee_client import decode_envelope
from cognee_retriever.projections import ProjectionBuilder, ProjectionStore


class MemoryCogneeClient:
    def __init__(self, *, fail_remember: bool = False) -> None:
        self.fail_remember = fail_remember
        self.datasets: dict[str, list[str]] = {}

    async def remember(self, texts: list[str], dataset_name: str) -> None:
        if self.fail_remember:
            raise RuntimeError("synthetic Cognee failure")
        self.datasets[dataset_name] = texts

    async def recall(self, query: str, dataset_name: str) -> list[dict[str, Any]]:
        del query
        values = self.datasets.get(dataset_name, [])
        return [decode_envelope(values[0])] if values else []


def file_hashes(directory: Path) -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.glob("*.jsonl"))
    }


@pytest.mark.asyncio
async def test_failed_rebuild_keeps_previous_projection_active(
    tmp_path: Path, manifest_directory: Path
) -> None:
    store = ProjectionStore(tmp_path / "projections.db")
    working_builder = ProjectionBuilder(MemoryCogneeClient(), store)
    previous = await working_builder.build("alpha", manifest_directory)

    failing_builder = ProjectionBuilder(MemoryCogneeClient(fail_remember=True), store)
    with pytest.raises(RuntimeError, match="synthetic Cognee failure"):
        await failing_builder.build("alpha", manifest_directory)

    active = await store.get_active("alpha")
    assert active is not None
    assert active.projection_id == previous.projection_id
    assert active.state == "active"


@pytest.mark.asyncio
async def test_rebuild_does_not_change_manifests_or_source_revisions(
    tmp_path: Path, manifest_directory: Path
) -> None:
    before = file_hashes(manifest_directory)
    store = ProjectionStore(tmp_path / "projections.db")
    builder = ProjectionBuilder(MemoryCogneeClient(), store)

    first = await builder.build("alpha", manifest_directory)
    second = await builder.build("alpha", manifest_directory)

    assert file_hashes(manifest_directory) == before
    assert second.source_revision_ids == first.source_revision_ids
    assert second.projection_id != first.projection_id
    assert (await store.get(first.projection_id)).state == "superseded"  # type: ignore[union-attr]
    assert (await store.get_active("alpha")).projection_id == second.projection_id  # type: ignore[union-attr]

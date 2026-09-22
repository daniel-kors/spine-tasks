"""Contract checks for the application-owned retrieval boundary."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from cognee_retriever.cognee_retriever import CogneeRetriever
from cognee_retriever.models import ProjectionVersion, RetrievalQuery
from cognee_retriever.projections import ProjectionStore


class FakeCogneeClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = payloads
        self.dataset_requested: str | None = None

    async def remember(self, texts: list[str], dataset_name: str) -> None:
        del texts, dataset_name

    async def recall(self, query: str, dataset_name: str) -> list[dict[str, Any]]:
        del query
        self.dataset_requested = dataset_name
        return self.payloads


def payload(
    *,
    source_id: str,
    chunk_id: str,
    scope: str,
    revision_id: UUID,
    workspace_id: str = "alpha",
    text: str = "1200 рублей",
) -> dict[str, Any]:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "workspace_id": workspace_id,
            "required_scope": scope,
            "source_id": source_id,
            "revision_id": str(revision_id),
            "chunk_id": chunk_id,
            "locator": {"path": f"{source_id}.md", "start_line": 1, "end_line": 1},
        },
    }


async def active_store(tmp_path: Path) -> tuple[ProjectionStore, ProjectionVersion]:
    store = ProjectionStore(tmp_path / "projections.db")
    await store.initialize()
    projection = ProjectionVersion(
        projection_id=uuid4(),
        workspace_id="alpha",
        dataset_name="alpha_projection_test",
        source_revision_ids=(),
        state="ready",
        created_at=datetime.now(UTC),
    )
    await store.save(projection)
    return store, await store.activate(projection.projection_id)


@pytest.mark.asyncio
async def test_adapter_maps_fake_cognee_payload(tmp_path: Path, revision_id: UUID) -> None:
    store, projection = await active_store(tmp_path)
    client = FakeCogneeClient(
        [
            payload(
                source_id="travel-policy",
                chunk_id="c1",
                scope="all-employees",
                revision_id=revision_id,
            )
        ]
    )

    result = await CogneeRetriever(client, store).retrieve(
        RetrievalQuery(
            workspace_id="alpha",
            user_id="u-1",
            scopes={"all-employees"},
            text="Какой размер суточных?",
        )
    )

    assert client.dataset_requested == projection.dataset_name
    assert result.index_version == str(projection.projection_id)
    assert result.chunks[0].reference.chunk_id == "c1"
    assert result.chunks[0].reference.source_id == "travel-policy"
    assert result.chunks[0].reference.locator["path"] == "travel-policy.md"


@pytest.mark.asyncio
async def test_forbidden_scope_and_other_workspace_are_absent(
    tmp_path: Path, revision_id: UUID
) -> None:
    store, _ = await active_store(tmp_path)
    client = FakeCogneeClient(
        [
            payload(
                source_id="public",
                chunk_id="c1",
                scope="all-employees",
                revision_id=revision_id,
            ),
            payload(
                source_id="secret",
                chunk_id="c2",
                scope="engineering",
                revision_id=revision_id,
            ),
            payload(
                source_id="other-workspace",
                chunk_id="c3",
                scope="all-employees",
                revision_id=revision_id,
                workspace_id="beta",
            ),
        ]
    )

    result = await CogneeRetriever(client, store).retrieve(
        RetrievalQuery(
            workspace_id="alpha",
            user_id="u-1",
            scopes={"all-employees"},
            text="policy",
        )
    )

    assert [chunk.reference.source_id for chunk in result.chunks] == ["public"]


@pytest.mark.asyncio
async def test_cognee_order_is_preserved(tmp_path: Path, revision_id: UUID) -> None:
    store, _ = await active_store(tmp_path)
    client = FakeCogneeClient(
        [
            payload(
                source_id="second",
                chunk_id="c2",
                scope="all-employees",
                revision_id=revision_id,
            ),
            payload(
                source_id="first",
                chunk_id="c1",
                scope="all-employees",
                revision_id=revision_id,
            ),
        ]
    )

    result = await CogneeRetriever(client, store).retrieve(
        RetrievalQuery(
            workspace_id="alpha", user_id="u-1", scopes={"all-employees"}, text="policy"
        )
    )

    assert [chunk.reference.chunk_id for chunk in result.chunks] == ["c2", "c1"]

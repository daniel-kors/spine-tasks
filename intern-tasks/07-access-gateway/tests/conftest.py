"""Synthetic chunks shared by access-gateway tests."""

from collections.abc import Callable
from uuid import UUID

import pytest

from access_gateway.models import ContextReference, RetrievedChunk

ChunkFactory = Callable[..., RetrievedChunk]


@pytest.fixture
def chunk_factory() -> ChunkFactory:
    def make(
        *,
        chunk_id: str = "engineering-name",
        source_id: str = "engineering-only",
        workspace_id: str = "alpha",
        required_scope: str = "engineering",
        text: str = "Кодовое имя прототипа — Aurora.",
    ) -> RetrievedChunk:
        return RetrievedChunk(
            workspace_id=workspace_id,
            required_scope=required_scope,
            text=text,
            reference=ContextReference(
                source_id=source_id,
                revision_id=UUID("33333333-3333-4333-8333-333333333333"),
                chunk_id=chunk_id,
                locator={"heading": "Кодовое имя", "paragraph": 1},
            ),
        )

    return make

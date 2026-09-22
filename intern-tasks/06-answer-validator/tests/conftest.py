"""Fixtures representing synthetic retrieved knowledge."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from answer_validator.models import ContextReference, RetrievedChunk


@pytest.fixture
def chunk_factory():
    def make(
        *,
        chunk_id: str = "travel-v2-daily",
        source_id: str = "travel-policy",
        revision_id: str = "11111111-1111-4111-8111-222222222222",
        text: str = "Суточные составляют 1200 рублей.",
        observed_at: datetime | None = datetime(2026, 9, 1, tzinfo=UTC),
    ) -> RetrievedChunk:
        return RetrievedChunk(
            workspace_id="alpha",
            required_scope="all-employees",
            text=text,
            reference=ContextReference(
                source_id=source_id,
                revision_id=UUID(revision_id),
                chunk_id=chunk_id,
                locator={"heading": "Суточные", "paragraph": 1},
            ),
            revision_observed_at=observed_at,
        )

    return make

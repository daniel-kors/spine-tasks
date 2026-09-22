"""Application-owned contracts for answer composition and validation."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContextReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    revision_id: UUID
    chunk_id: str = Field(min_length=1)
    locator: dict[str, str | int | None]


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    required_scope: str = Field(min_length=1)
    text: str = Field(min_length=1)
    reference: ContextReference
    revision_observed_at: datetime | None = None

    @field_validator("revision_observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("revision_observed_at must include a timezone")
        return value.astimezone(UTC)


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    citation_ids: tuple[str, ...]


class DraftAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claims: tuple[Claim, ...]
    summary: str = Field(min_length=1)


class ValidatedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["answered", "abstained"]
    answer_text: str | None
    citations: tuple[ContextReference, ...]
    reasons: tuple[str, ...]

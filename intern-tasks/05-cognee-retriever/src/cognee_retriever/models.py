"""Application-owned retrieval and projection contracts."""

from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    scopes: frozenset[str]
    text: str = Field(min_length=1, max_length=2000)


class ContextReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    revision_id: UUID
    chunk_id: str
    locator: dict[str, str | int | None]


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    required_scope: str
    text: str
    reference: ContextReference


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunks: tuple[RetrievedChunk, ...]
    strategy: str
    index_version: str


class ManifestChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    required_scope: str
    text: str
    reference: ContextReference


class ProjectionVersion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    projection_id: UUID
    workspace_id: str
    dataset_name: str
    source_revision_ids: tuple[UUID, ...]
    state: Literal["building", "ready", "active", "superseded", "failed"]
    created_at: datetime
    error_description: str | None = None

    @field_validator("created_at")
    @classmethod
    def timestamp_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return value


class BuildRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    manifests: Path
    activate: bool = True


class ManualCheckCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    workspace_id: str
    scopes: frozenset[str]
    question: str
    expected_source_ids: frozenset[str]
    forbidden_source_ids: frozenset[str]


class ManualCheckResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    expected_source_found: bool
    forbidden_source_absent: bool
    duration_ms: float = Field(ge=0)
    references_restorable: bool

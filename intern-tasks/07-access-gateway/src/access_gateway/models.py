"""Application-owned access, retrieval, and audit contracts."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Subject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: str
    workspace_id: str = Field(min_length=1)
    scopes: frozenset[str] = frozenset()


class AccessDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    reason_code: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    user_id: str
    scopes: frozenset[str]
    text: str = Field(min_length=1, max_length=2000)


class ContextReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    revision_id: UUID
    chunk_id: str = Field(min_length=1)
    locator: dict[str, str | int | None]


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    required_scope: str
    text: str = Field(min_length=1)
    reference: ContextReference


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunks: tuple[RetrievedChunk, ...]
    strategy: str = Field(min_length=1)
    index_version: str = Field(min_length=1)
    policy_version: str | None = None


class SecurityEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "knowledge_access_denied"
    occurred_at: datetime
    user_id: str
    subject_workspace_id: str
    chunk_workspace_id: str
    source_id: str
    revision_id: UUID
    chunk_id: str
    required_scope: str
    reason_code: str
    policy_version: str

    @field_validator("occurred_at")
    @classmethod
    def timestamp_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(UTC)

"""Application-owned HTTP and service contracts."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AskRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    scopes: frozenset[str] = Field(min_length=1, max_length=20)
    question: str = Field(min_length=1, max_length=2000)
    request_id: str = Field(min_length=1, max_length=200)

    @field_validator("workspace_id", "user_id", "question", "request_id")
    @classmethod
    def text_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class Subject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    user_id: str
    scopes: frozenset[str]


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
    index_version: str
    policy_version: str


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    citation_ids: tuple[str, ...]


class DraftAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claims: tuple[Claim, ...]
    summary: str


class ValidatedAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["answered", "abstained"]
    answer_text: str | None
    citations: tuple[ContextReference, ...]
    reasons: tuple[str, ...]


class AskResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["answered", "abstained"]
    answer: str | None
    citations: tuple[ContextReference, ...]
    index_version: str
    policy_version: str
    trace_id: UUID
    as_of: datetime
    reasons: tuple[str, ...]

    @field_validator("as_of")
    @classmethod
    def as_of_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include a timezone")
        return value.astimezone(UTC)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str
    trace_id: UUID
    retryable: bool

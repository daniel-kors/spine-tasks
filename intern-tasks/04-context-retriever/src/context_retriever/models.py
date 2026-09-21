"""Application-owned contracts for knowledge retrieval."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
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
    required_scope: str = Field(min_length=1)
    text: str = Field(min_length=1)
    reference: ContextReference


class RetrievalResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunks: tuple[RetrievedChunk, ...]
    strategy: str = Field(min_length=1)
    index_version: str = Field(min_length=1)

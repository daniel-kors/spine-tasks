"""Validated contracts for ingestion commands and receipts."""

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    directory: Path
    idempotency_key: str = Field(min_length=1)


class ItemReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    status: Literal["indexed", "unchanged", "failed"]
    revision_id: UUID | None
    chunk_count: int = Field(ge=0)
    error_code: str | None


class IngestionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID
    workspace_id: str
    items: tuple[ItemReceipt, ...]


class RevisionRegistration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["created", "unchanged"]
    revision_id: UUID


class ChunkDescription(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str
    workspace_id: str
    source_id: str
    revision_id: UUID
    ordinal: int = Field(ge=0)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)

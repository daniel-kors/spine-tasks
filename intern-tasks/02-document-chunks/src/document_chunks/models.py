"""Validated document and chunk contracts."""

from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    revision_id: UUID
    path: Path
    media_type: str = Field(min_length=1)


class TextLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    heading: str | None
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)

    @model_validator(mode="after")
    def end_follows_start(self) -> "TextLocator":
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class ParsedChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str = Field(min_length=64, max_length=64)
    workspace_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    revision_id: UUID
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    locator: TextLocator

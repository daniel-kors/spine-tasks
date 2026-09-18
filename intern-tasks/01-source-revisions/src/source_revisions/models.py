"""Validated contracts shared by the service and repositories."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class SourceRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision_id: UUID
    workspace_id: str
    source_id: str
    checksum_sha256: str
    media_type: str
    original_path: str
    observed_at: datetime
    is_tombstone: bool = False

    @field_validator("workspace_id", "source_id", "media_type", "original_path")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    @field_validator("checksum_sha256")
    @classmethod
    def valid_checksum(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("checksum_sha256 must be a lowercase SHA-256 hex digest")
        return value

    @field_validator("observed_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must have a timezone")
        return value.astimezone(UTC)


class RegisterResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["created", "unchanged"]
    revision: SourceRevision

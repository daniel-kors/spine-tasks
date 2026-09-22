"""Pydantic contracts passed between workflow, activities, and clients."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReindexInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str = Field(min_length=1)
    projection_id: str = Field(min_length=1)
    manifest_paths: tuple[str, ...]


class ReindexProgress(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["pending", "running", "activated", "cancelled", "failed"]
    processed: int = Field(ge=0)
    total: int = Field(ge=0)
    cancel_requested: bool


class ReindexResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["activated", "cancelled", "failed"]
    projection_id: str
    indexed_count: int = Field(ge=0)


class ValidateManifestsInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    projection_id: str
    manifest_paths: tuple[str, ...]


class ProjectionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    projection_id: str
    expected_count: int = Field(ge=0)


class IndexBatchInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    projection_id: str
    manifest_paths: tuple[str, ...] = Field(min_length=1, max_length=10)
    batch_number: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1)


class MarkFailedInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    projection_id: str
    reason_code: str

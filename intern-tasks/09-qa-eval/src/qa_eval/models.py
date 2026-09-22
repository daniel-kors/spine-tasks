"""Validated contracts for datasets, system results, and reports."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvalCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    scopes: frozenset[str]
    question: str = Field(min_length=1)
    expected_status: Literal["answered", "abstained"]
    expected_source_ids: frozenset[str]
    expected_revision_ids: frozenset[UUID] = frozenset()
    required_facts: tuple[str, ...]
    required_patterns: tuple[str, ...] = ()
    forbidden_source_ids: frozenset[str]

    @field_validator("case_id", "workspace_id", "question")
    @classmethod
    def text_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class QaQuery(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace_id: str
    scopes: frozenset[str]
    question: str


class ContextReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    revision_id: UUID
    chunk_id: str
    locator: dict[str, str | int | None]


class ContextChunk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    reference: ContextReference


class QaResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["answered", "abstained"]
    answer: str | None
    context: tuple[ContextChunk, ...]
    citations: tuple[ContextReference, ...]
    index_version: str


class Failure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    code: str
    expected: str
    actual: str


class CaseEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    duration_ms: float = Field(ge=0)
    status_correct: bool
    expected_sources_present: bool
    citations_valid: bool
    forbidden_sources: frozenset[str]
    required_content_present: bool
    failures: tuple[Failure, ...]
    index_version: str | None


class Metrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_cases: int
    forbidden_source_count: int
    citation_validity_rate: float
    expected_source_rate: float
    status_accuracy: float
    required_content_rate: float
    average_duration_ms: float


class EvaluationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str
    adapter_name: str
    projection_versions: tuple[str, ...]
    run_at: datetime
    ready: bool
    metrics: Metrics
    cases: tuple[CaseEvaluation, ...]
    failures: tuple[Failure, ...]

    @field_validator("run_at")
    @classmethod
    def run_at_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run_at must include a timezone")
        return value.astimezone(UTC)

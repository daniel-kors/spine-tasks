"""Small hand-built evaluation contracts."""

from collections.abc import Callable
from uuid import UUID

import pytest

from qa_eval.models import ContextChunk, ContextReference, EvalCase, QaResult


@pytest.fixture
def case_factory() -> Callable[..., EvalCase]:
    def make(**updates: object) -> EvalCase:
        values: dict[str, object] = {
            "schema_version": "1.0",
            "case_id": "travel-01",
            "workspace_id": "alpha",
            "scopes": {"all-employees"},
            "question": "Какой размер суточных?",
            "expected_status": "answered",
            "expected_source_ids": {"travel-policy"},
            "required_facts": ("1200 рублей",),
            "forbidden_source_ids": {"engineering-only"},
        }
        values.update(updates)
        return EvalCase.model_validate(values)

    return make


@pytest.fixture
def reference_factory() -> Callable[..., ContextReference]:
    def make(**updates: object) -> ContextReference:
        values: dict[str, object] = {
            "source_id": "travel-policy",
            "revision_id": UUID("11111111-1111-4111-8111-222222222222"),
            "chunk_id": "travel-c1",
            "locator": {"heading": "Суточные", "paragraph": 1},
        }
        values.update(updates)
        return ContextReference.model_validate(values)

    return make


@pytest.fixture
def result_factory(
    reference_factory: Callable[..., ContextReference],
) -> Callable[..., QaResult]:
    def make(**updates: object) -> QaResult:
        reference = reference_factory()
        values: dict[str, object] = {
            "status": "answered",
            "answer": "Суточные составляют 1200 рублей.",
            "context": (ContextChunk(text="1200 рублей", reference=reference),),
            "citations": (reference,),
            "index_version": "projection-v1",
        }
        values.update(updates)
        return QaResult.model_validate(values)

    return make

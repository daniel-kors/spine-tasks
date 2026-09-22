"""Pure check and threshold behavior."""

from collections.abc import Callable

from qa_eval.checks import evaluate_case, expected_sources_found, forbidden_sources_found
from qa_eval.models import (
    ContextChunk,
    ContextReference,
    EvalCase,
    QaResult,
)
from qa_eval.runner import build_report


def test_expected_sources_are_order_independent() -> None:
    assert expected_sources_found({"travel", "security"}, {"other", "security", "travel"})
    assert not expected_sources_found({"travel"}, {"security", "other"})
    assert expected_sources_found(set(), {"anything"})


def test_forbidden_sources_returns_exact_intersection() -> None:
    assert forbidden_sources_found(
        {"engineering-only", "finance-only"},
        {"travel-policy", "engineering-only"},
    ) == {"engineering-only"}


def test_hand_built_good_result_is_recognized(
    case_factory: Callable[..., EvalCase],
    result_factory: Callable[..., QaResult],
) -> None:
    case = case_factory()
    evaluation = evaluate_case(case, result_factory(), duration_ms=12.5)
    report = build_report((case,), (evaluation,), "hand-built")

    assert evaluation.failures == ()
    assert evaluation.citations_valid is True
    assert evaluation.expected_sources_present is True
    assert report.ready is True


def test_fabricated_citation_fails_readiness(
    case_factory: Callable[..., EvalCase],
    result_factory: Callable[..., QaResult],
    reference_factory: Callable[..., ContextReference],
) -> None:
    case = case_factory()
    fabricated = reference_factory(chunk_id="missing-chunk")
    result = result_factory(citations=(fabricated,))
    evaluation = evaluate_case(case, result, duration_ms=1)
    report = build_report((case,), (evaluation,), "fabricated")

    assert "INVALID_CITATION" in {failure.code for failure in evaluation.failures}
    assert report.metrics.citation_validity_rate == 0
    assert report.ready is False


def test_one_forbidden_source_fails_regardless_of_other_results(
    case_factory: Callable[..., EvalCase],
    result_factory: Callable[..., QaResult],
    reference_factory: Callable[..., ContextReference],
) -> None:
    good_case = case_factory(case_id="good")
    leaked_case = case_factory(case_id="leaked")
    good = evaluate_case(good_case, result_factory(), duration_ms=1)
    leaked_reference = reference_factory(
        source_id="engineering-only",
        chunk_id="engineering-leak",
    )
    base = result_factory()
    leaked_result = base.model_copy(
        update={
            "context": (
                *base.context,
                ContextChunk(text="закрытый текст", reference=leaked_reference),
            ),
        }
    )
    leaked = evaluate_case(leaked_case, leaked_result, duration_ms=1)
    report = build_report((good_case, leaked_case), (good, leaked), "one-leak")

    assert report.metrics.forbidden_source_count == 1
    assert report.metrics.status_accuracy == 1
    assert report.metrics.expected_source_rate == 1
    assert report.ready is False


def test_missing_expected_source_is_detected_among_other_positions(
    case_factory: Callable[..., EvalCase],
    result_factory: Callable[..., QaResult],
    reference_factory: Callable[..., ContextReference],
) -> None:
    case = case_factory()
    first = reference_factory(source_id="first", chunk_id="first-c1")
    last = reference_factory(source_id="last", chunk_id="last-c1")
    result = result_factory(
        context=(
            ContextChunk(text="первый", reference=first),
            ContextChunk(text="последний", reference=last),
        ),
        citations=(first,),
    )

    evaluation = evaluate_case(case, result, duration_ms=1)

    assert evaluation.expected_sources_present is False
    assert "EXPECTED_SOURCE_MISSING" in {failure.code for failure in evaluation.failures}

"""Small pure checks used by the evaluation runner."""

import re

from .models import CaseEvaluation, EvalCase, Failure, QaResult


def expected_sources_found(expected: set[str], actual: set[str]) -> bool:
    return not expected or expected.issubset(actual)


def forbidden_sources_found(forbidden: set[str], actual: set[str]) -> set[str]:
    return forbidden & actual


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def evaluate_case(case: EvalCase, result: QaResult, duration_ms: float) -> CaseEvaluation:
    failures: list[Failure] = []
    context_sources = {chunk.reference.source_id for chunk in result.context}
    citation_sources = {reference.source_id for reference in result.citations}
    all_sources = context_sources | citation_sources

    sources_present = expected_sources_found(set(case.expected_source_ids), context_sources)
    if not sources_present:
        failures.append(
            _failure(
                case,
                "EXPECTED_SOURCE_MISSING",
                sorted(case.expected_source_ids),
                sorted(context_sources),
            )
        )

    forbidden = forbidden_sources_found(set(case.forbidden_source_ids), all_sources)
    if forbidden:
        failures.append(_failure(case, "FORBIDDEN_SOURCE", [], sorted(forbidden)))

    citations_valid, citation_failures = _validate_citations(case, result)
    failures.extend(citation_failures)

    status_correct = result.status == case.expected_status
    if not status_correct:
        failures.append(
            _failure(case, "STATUS_MISMATCH", case.expected_status, result.status)
        )

    revision_failures = _validate_expected_revisions(case, result)
    failures.extend(revision_failures)

    content_present, content_failures = _validate_required_content(case, result.answer)
    failures.extend(content_failures)

    return CaseEvaluation(
        case_id=case.case_id,
        duration_ms=duration_ms,
        status_correct=status_correct,
        expected_sources_present=sources_present,
        citations_valid=citations_valid,
        forbidden_sources=frozenset(forbidden),
        required_content_present=content_present,
        failures=tuple(failures),
        index_version=result.index_version,
    )


def _validate_citations(case: EvalCase, result: QaResult) -> tuple[bool, list[Failure]]:
    failures: list[Failure] = []
    if result.status == "answered" and not result.citations:
        failures.append(_failure(case, "CITATIONS_MISSING", "at least one", "none"))
    for citation in result.citations:
        matches = [
            chunk.reference
            for chunk in result.context
            if chunk.reference.chunk_id == citation.chunk_id
        ]
        if citation not in matches:
            failures.append(
                _failure(
                    case,
                    "INVALID_CITATION",
                    "exact context reference",
                    citation.model_dump(mode="json"),
                )
            )
    return not failures, failures


def _validate_expected_revisions(case: EvalCase, result: QaResult) -> list[Failure]:
    if not case.expected_revision_ids:
        return []
    actual = {
        chunk.reference.revision_id
        for chunk in result.context
        if chunk.reference.source_id in case.expected_source_ids
    }
    if actual and actual.issubset(case.expected_revision_ids):
        return []
    return [
        _failure(
            case,
            "UNEXPECTED_REVISION",
            sorted(str(item) for item in case.expected_revision_ids),
            sorted(str(item) for item in actual),
        )
    ]


def _validate_required_content(case: EvalCase, answer: str | None) -> tuple[bool, list[Failure]]:
    normalized = normalize_text(answer or "")
    failures: list[Failure] = []
    for fact in case.required_facts:
        if normalize_text(fact) not in normalized:
            failures.append(_failure(case, "REQUIRED_FACT_MISSING", fact, answer or ""))
    for pattern in case.required_patterns:
        if re.search(pattern, answer or "", flags=re.IGNORECASE) is None:
            failures.append(_failure(case, "REQUIRED_PATTERN_MISSING", pattern, answer or ""))
    return not failures, failures


def _failure(case: EvalCase, code: str, expected: object, actual: object) -> Failure:
    return Failure(
        case_id=case.case_id,
        code=code,
        expected=str(expected),
        actual=str(actual),
    )

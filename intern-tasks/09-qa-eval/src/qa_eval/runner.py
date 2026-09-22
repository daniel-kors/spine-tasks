"""Run every case, continue after item errors, and apply readiness thresholds."""

from datetime import UTC, datetime
from time import perf_counter

from .checks import evaluate_case
from .models import (
    CaseEvaluation,
    EvalCase,
    EvaluationReport,
    Failure,
    Metrics,
    QaQuery,
)
from .system import QaSystem


class EvaluationRunner:
    def __init__(self, system: QaSystem) -> None:
        self.system = system

    async def run(self, cases: tuple[EvalCase, ...]) -> EvaluationReport:
        evaluations: list[CaseEvaluation] = []
        for case in cases:
            started = perf_counter()
            try:
                result = await self.system.ask(
                    QaQuery(
                        workspace_id=case.workspace_id,
                        scopes=case.scopes,
                        question=case.question,
                    )
                )
                duration_ms = (perf_counter() - started) * 1000
                evaluation = evaluate_case(case, result, duration_ms)
            except Exception as exc:
                duration_ms = (perf_counter() - started) * 1000
                failure = Failure(
                    case_id=case.case_id,
                    code="SYSTEM_ERROR",
                    expected="successful controlled result",
                    actual=type(exc).__name__,
                )
                evaluation = CaseEvaluation(
                    case_id=case.case_id,
                    duration_ms=duration_ms,
                    status_correct=False,
                    expected_sources_present=False,
                    citations_valid=False,
                    forbidden_sources=frozenset(),
                    required_content_present=False,
                    failures=(failure,),
                    index_version=None,
                )
            evaluations.append(evaluation)
        return build_report(cases, tuple(evaluations), self.system.name)


def build_report(
    cases: tuple[EvalCase, ...],
    evaluations: tuple[CaseEvaluation, ...],
    adapter_name: str,
) -> EvaluationReport:
    metrics = calculate_metrics(cases, evaluations)
    failures = tuple(failure for item in evaluations for failure in item.failures)
    ready = (
        metrics.forbidden_source_count == 0
        and metrics.citation_validity_rate == 1.0
        and metrics.expected_source_rate >= 0.85
        and metrics.status_accuracy >= 0.80
    )
    return EvaluationReport(
        dataset_version=cases[0].schema_version,
        adapter_name=adapter_name,
        projection_versions=tuple(
            sorted({item.index_version for item in evaluations if item.index_version})
        ),
        run_at=datetime.now(UTC),
        ready=ready,
        metrics=metrics,
        cases=evaluations,
        failures=failures,
    )


def calculate_metrics(
    cases: tuple[EvalCase, ...], evaluations: tuple[CaseEvaluation, ...]
) -> Metrics:
    by_id = {item.case_id: item for item in evaluations}
    expected_applicable = [case for case in cases if case.expected_source_ids]
    expected_passed = sum(
        by_id[case.case_id].expected_sources_present for case in expected_applicable
    )
    total = len(evaluations)
    return Metrics(
        total_cases=total,
        forbidden_source_count=sum(len(item.forbidden_sources) for item in evaluations),
        citation_validity_rate=sum(item.citations_valid for item in evaluations) / total,
        expected_source_rate=(
            expected_passed / len(expected_applicable) if expected_applicable else 1.0
        ),
        status_accuracy=sum(item.status_correct for item in evaluations) / total,
        required_content_rate=sum(item.required_content_present for item in evaluations) / total,
        average_duration_ms=sum(item.duration_ms for item in evaluations) / total,
    )

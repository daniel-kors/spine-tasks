"""Run prepared questions while persisting metrics without answer text."""

from pathlib import Path
from time import perf_counter
from typing import Protocol

from .models import ManualCheckCase, ManualCheckResult, RetrievalQuery, RetrievalResult


class Retriever(Protocol):
    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult: ...


def read_cases(path: Path) -> tuple[ManualCheckCase, ...]:
    with path.open("r", encoding="utf-8") as stream:
        return tuple(
            ManualCheckCase.model_validate_json(line) for line in stream if line.strip()
        )


async def run_manual_checks(
    retriever: Retriever,
    cases_path: Path,
    output_path: Path,
    *,
    user_id: str,
) -> tuple[ManualCheckResult, ...]:
    results: list[ManualCheckResult] = []
    for case in read_cases(cases_path):
        started = perf_counter()
        retrieval = await retriever.retrieve(
            RetrievalQuery(
                workspace_id=case.workspace_id,
                user_id=user_id,
                scopes=case.scopes,
                text=case.question,
            )
        )
        duration_ms = (perf_counter() - started) * 1000
        source_ids = {chunk.reference.source_id for chunk in retrieval.chunks}
        results.append(
            ManualCheckResult(
                case_id=case.case_id,
                expected_source_found=case.expected_source_ids.issubset(source_ids),
                forbidden_source_absent=not bool(case.forbidden_source_ids & source_ids),
                duration_ms=round(duration_ms, 3),
                references_restorable=all(
                    bool(chunk.reference.source_id)
                    and bool(chunk.reference.chunk_id)
                    and bool(chunk.reference.locator)
                    for chunk in retrieval.chunks
                ),
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as stream:
        for result in results:
            stream.write(result.model_dump_json() + "\n")
    return tuple(results)

"""Load and fully validate a JSONL evaluation dataset."""

import re
from pathlib import Path

from pydantic import ValidationError

from .models import EvalCase


def load_eval_cases(path: Path) -> tuple[EvalCase, ...]:
    cases: list[EvalCase] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                case = EvalCase.model_validate_json(line)
            except ValidationError as exc:
                raise ValueError(f"Invalid case at line {line_number}: {exc}") from exc
            if case.case_id in seen:
                raise ValueError(f"Duplicate case_id at line {line_number}: {case.case_id}")
            for pattern in case.required_patterns:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ValueError(
                        f"Invalid required_patterns value at line {line_number}: {pattern}"
                    ) from exc
            seen.add(case.case_id)
            cases.append(case)
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    versions = {case.schema_version for case in cases}
    if len(versions) != 1:
        raise ValueError(f"Dataset contains multiple schema versions: {sorted(versions)}")
    return tuple(cases)

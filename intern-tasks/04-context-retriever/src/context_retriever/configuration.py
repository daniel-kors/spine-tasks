"""Load prepared synthetic data and convert it to fake retriever inputs."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import RetrievalResult, RetrievedChunk


class ContextProviderUnavailableError(RuntimeError):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class FakeConfiguration:
    answers: dict[str, RetrievalResult]
    errors: dict[str, Exception]


def load_fake_configuration(path: Path) -> FakeConfiguration:
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    allowed = {"schema_version", "index_version", "answers", "errors"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"Unknown fake configuration fields: {sorted(unknown)}")
    index_version = str(payload["index_version"])
    answers = {
        question: RetrievalResult(
            chunks=tuple(RetrievedChunk.model_validate(chunk) for chunk in chunks),
            strategy="configured-fake",
            index_version=index_version,
        )
        for question, chunks in payload["answers"].items()
    }
    errors = {
        question: ContextProviderUnavailableError(str(error_code))
        for question, error_code in payload.get("errors", {}).items()
    }
    return FakeConfiguration(answers=answers, errors=errors)

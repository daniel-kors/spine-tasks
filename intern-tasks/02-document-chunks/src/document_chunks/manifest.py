"""JSONL persistence and locator verification for parsed chunks."""

from pathlib import Path

from pydantic import ValidationError

from .models import ParsedChunk
from .parser import DocumentDecodeError


class ManifestError(Exception):
    """A manifest is malformed or does not match its source document."""


def write_manifest(path: Path, chunks: tuple[ParsedChunk, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for chunk in chunks:
            stream.write(chunk.model_dump_json() + "\n")
    temporary.replace(path)


def read_manifest(path: Path) -> tuple[ParsedChunk, ...]:
    chunks: list[ParsedChunk] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    chunks.append(ParsedChunk.model_validate_json(line))
                except ValidationError as exc:
                    raise ManifestError(
                        f"Invalid manifest line {line_number} in {path}: {exc}"
                    ) from exc
    except UnicodeDecodeError as exc:
        raise ManifestError(f"Manifest is not valid UTF-8: {path}") from exc
    if not chunks:
        raise ManifestError(f"Manifest contains no chunks: {path}")
    return tuple(chunks)


def verify_manifest(source_path: Path, manifest_path: Path) -> int:
    try:
        original = source_path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentDecodeError(f"Document is not valid UTF-8: {source_path}") from exc

    chunks = read_manifest(manifest_path)
    for line_number, chunk in enumerate(chunks, start=1):
        locator = chunk.locator
        actual = original[locator.char_start : locator.char_end]
        if actual != chunk.text:
            raise ManifestError(
                f"Locator mismatch at manifest line {line_number}: "
                f"source[{locator.char_start}:{locator.char_end}] does not match chunk text"
            )
    return len(chunks)

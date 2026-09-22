"""Derive stable JSONL chunk manifests from the copied synthetic documents."""

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"
MANIFESTS = FIXTURES / "manifests"
HEADING_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*(?:\r?\n|$)")
PARAGRAPH_SEPARATOR_RE = re.compile(r"\r?\n[ \t]*\r?\n+")


def sections(original: str) -> list[tuple[str | None, int, int]]:
    headings = list(HEADING_RE.finditer(original))
    if not headings:
        return [(None, 0, len(original))]
    result: list[tuple[str | None, int, int]] = []
    if original[: headings[0].start()].strip():
        result.append((None, 0, headings[0].start()))
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(original)
        result.append((match.group("title").strip(), match.end(), end))
    return result


def paragraphs(original: str, start: int, end: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    cursor = start
    boundaries: list[tuple[int, int]] = []
    for separator in PARAGRAPH_SEPARATOR_RE.finditer(original, start, end):
        boundaries.append((cursor, separator.start()))
        cursor = separator.end()
    boundaries.append((cursor, end))
    for paragraph_start, paragraph_end in boundaries:
        while paragraph_start < paragraph_end and original[paragraph_start].isspace():
            paragraph_start += 1
        while paragraph_end > paragraph_start and original[paragraph_end - 1].isspace():
            paragraph_end -= 1
        if paragraph_start < paragraph_end:
            result.append((paragraph_start, paragraph_end))
    return result


def chunk_document(source: dict[str, Any]) -> list[dict[str, Any]]:
    path = FIXTURES / source["file"]
    original = path.read_bytes().decode("utf-8")
    chunks: list[dict[str, Any]] = []
    for heading, section_start, section_end in sections(original):
        for start, end in paragraphs(original, section_start, section_end):
            text = original[start:end]
            ordinal = len(chunks)
            chunk_id = sha256(
                f"{source['revision_id']}\x00{ordinal}\x00{text}".encode()
            ).hexdigest()
            chunks.append(
                {
                    "workspace_id": source["workspace_id"],
                    "required_scope": source["required_scope"],
                    "text": text,
                    "reference": {
                        "source_id": source["source_id"],
                        "revision_id": source["revision_id"],
                        "chunk_id": chunk_id,
                        "locator": {
                            "heading": heading,
                            "char_start": start,
                            "char_end": end,
                        },
                    },
                }
            )
    return chunks


def main() -> None:
    access_map = json.loads((FIXTURES / "access-map.json").read_text(encoding="utf-8"))
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    for source in access_map["sources"]:
        if not source["current"]:
            continue
        chunks = chunk_document(source)
        output = MANIFESTS / f"{source['revision_id']}.jsonl"
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            for chunk in chunks:
                stream.write(json.dumps(chunk, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()

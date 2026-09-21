"""Tests for document splitting and exact source locators."""

from pathlib import Path
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from document_chunks.markdown_parser import MarkdownParser
from document_chunks.models import SourceDocument
from document_chunks.parser import DocumentDecodeError, EmptyDocumentError

REVISION_ID = UUID("11111111-1111-4111-8111-222222222222")


def make_document(path: Path, media_type: str = "text/markdown") -> SourceDocument:
    return SourceDocument(
        workspace_id="alpha",
        source_id="policy",
        revision_id=REVISION_ID,
        path=path,
        media_type=media_type,
    )


def assert_exact_locators(original: str, chunks: tuple) -> None:
    for chunk in chunks:
        locator = chunk.locator
        assert original[locator.char_start : locator.char_end] == chunk.text


def test_each_locator_returns_exact_original_text(tmp_path: Path) -> None:
    original = "# Раздел\n\nПервый абзац.\n\nВторой абзац.\n"
    path = tmp_path / "policy.md"
    path.write_bytes(original.encode("utf-8"))

    chunks = MarkdownParser(max_chars=25).parse(make_document(path))

    assert [chunk.locator.heading for chunk in chunks] == ["Раздел", "Раздел"]
    assert_exact_locators(original, chunks)


def test_repeated_parse_produces_same_chunk_ids(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("# Правила\n\nОдин абзац.\n\nДругой абзац.", encoding="utf-8")
    parser = MarkdownParser(max_chars=20)

    first = parser.parse(make_document(path))
    second = parser.parse(make_document(path))

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_identical_paragraphs_have_distinct_ordinals_and_locators(tmp_path: Path) -> None:
    original = "Повтор.\n\nПовтор."
    path = tmp_path / "policy.txt"
    path.write_text(original, encoding="utf-8")

    chunks = MarkdownParser(max_chars=8).parse(make_document(path, "text/plain"))

    assert [chunk.text for chunk in chunks] == ["Повтор.", "Повтор."]
    assert [chunk.ordinal for chunk in chunks] == [0, 1]
    assert chunks[0].locator.char_start != chunks[1].locator.char_start
    assert chunks[0].chunk_id != chunks[1].chunk_id


def test_unicode_and_windows_newlines_keep_exact_positions(tmp_path: Path) -> None:
    original = "# Команда 🚀\r\n\r\nСотрудник может работать удалённо.\r\n\r\nКафе — рядом."
    path = tmp_path / "unicode.md"
    path.write_bytes(original.encode("utf-8"))

    chunks = MarkdownParser(max_chars=45).parse(make_document(path))

    assert_exact_locators(original, chunks)
    assert any("🚀" in (chunk.locator.heading or "") for chunk in chunks)


def test_limit_is_exceeded_only_by_an_indivisible_word(tmp_path: Path) -> None:
    long_word = "сверхдлинноесловобезпробелов"
    original = f"короткие слова здесь {long_word} конец"
    path = tmp_path / "policy.txt"
    path.write_text(original, encoding="utf-8")

    chunks = MarkdownParser(max_chars=15).parse(make_document(path, "text/plain"))

    assert all(len(chunk.text) <= 15 or chunk.text == long_word for chunk in chunks)
    assert_exact_locators(original, chunks)


def test_empty_file_raises_typed_error_without_fake_chunk(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    path.write_text("", encoding="utf-8")

    with pytest.raises(EmptyDocumentError):
        MarkdownParser().parse(make_document(path))


def test_invalid_utf8_raises_typed_error(tmp_path: Path) -> None:
    path = tmp_path / "invalid.md"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(DocumentDecodeError):
        MarkdownParser().parse(make_document(path))


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.text(min_size=1).filter(lambda value: "\x00" not in value and bool(value.strip())))
def test_locator_round_trip(tmp_path: Path, text: str) -> None:
    path = tmp_path / "generated.txt"
    path.write_text(text, encoding="utf-8", newline="")

    chunks = MarkdownParser(max_chars=80).parse(make_document(path, "text/plain"))

    assert_exact_locators(text, chunks)

"""Markdown and plain-text parsing with exact character locators."""

import re
from hashlib import sha256

from .models import ParsedChunk, SourceDocument, TextLocator
from .parser import DocumentDecodeError, EmptyDocumentError, UnsupportedMediaTypeError

HEADING_RE = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+(?P<title>.+?)[ \t]*#*[ \t]*(?:\r?\n|$)")
PARAGRAPH_SEPARATOR_RE = re.compile(r"\r?\n[ \t]*\r?\n+")
WORD_RE = re.compile(r"\S+")
SUPPORTED_MEDIA_TYPES = {"text/markdown", "text/plain"}


class MarkdownParser:
    def __init__(self, max_chars: int = 600) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be positive")
        self.max_chars = max_chars

    def parse(self, document: SourceDocument) -> tuple[ParsedChunk, ...]:
        if document.media_type not in SUPPORTED_MEDIA_TYPES:
            raise UnsupportedMediaTypeError(f"Unsupported media type: {document.media_type}")
        try:
            original = document.path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentDecodeError(f"Document is not valid UTF-8: {document.path}") from exc

        spans = self._content_spans(original, document.media_type == "text/markdown")
        chunks: list[ParsedChunk] = []
        for heading, start, end in spans:
            for chunk_start, chunk_end in self._split_span(original, start, end):
                text = original[chunk_start:chunk_end]
                ordinal = len(chunks)
                locator = TextLocator(
                    heading=heading,
                    char_start=chunk_start,
                    char_end=chunk_end,
                )
                chunk = ParsedChunk(
                    chunk_id=self._chunk_id(str(document.revision_id), ordinal, text),
                    workspace_id=document.workspace_id,
                    source_id=document.source_id,
                    revision_id=document.revision_id,
                    ordinal=ordinal,
                    text=text,
                    locator=locator,
                )
                assert original[locator.char_start : locator.char_end] == chunk.text
                chunks.append(chunk)

        if not chunks:
            raise EmptyDocumentError(f"Document contains no text: {document.path}")
        return tuple(chunks)

    def _content_spans(self, original: str, markdown: bool) -> list[tuple[str | None, int, int]]:
        if not markdown:
            return [(None, 0, len(original))]
        headings = list(HEADING_RE.finditer(original))
        if not headings:
            return [(None, 0, len(original))]

        spans: list[tuple[str | None, int, int]] = []
        if original[: headings[0].start()].strip():
            spans.append((None, 0, headings[0].start()))
        for index, match in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(original)
            spans.append((match.group("title").strip(), match.end(), end))
        return spans

    def _split_span(self, original: str, start: int, end: int) -> list[tuple[int, int]]:
        paragraphs = self._paragraph_spans(original, start, end)
        result: list[tuple[int, int]] = []
        pending: tuple[int, int] | None = None
        for paragraph_start, paragraph_end in paragraphs:
            if paragraph_end - paragraph_start > self.max_chars:
                if pending is not None:
                    result.append(pending)
                    pending = None
                result.extend(self._split_long_text(original, paragraph_start, paragraph_end))
            elif pending is None:
                pending = (paragraph_start, paragraph_end)
            elif paragraph_end - pending[0] <= self.max_chars:
                pending = (pending[0], paragraph_end)
            else:
                result.append(pending)
                pending = (paragraph_start, paragraph_end)
        if pending is not None:
            result.append(pending)
        return result

    @staticmethod
    def _paragraph_spans(original: str, start: int, end: int) -> list[tuple[int, int]]:
        boundaries: list[tuple[int, int]] = []
        cursor = start
        for separator in PARAGRAPH_SEPARATOR_RE.finditer(original, start, end):
            boundaries.append((cursor, separator.start()))
            cursor = separator.end()
        boundaries.append((cursor, end))

        paragraphs: list[tuple[int, int]] = []
        for paragraph_start, paragraph_end in boundaries:
            while paragraph_start < paragraph_end and original[paragraph_start].isspace():
                paragraph_start += 1
            while paragraph_end > paragraph_start and original[paragraph_end - 1].isspace():
                paragraph_end -= 1
            if paragraph_start < paragraph_end:
                paragraphs.append((paragraph_start, paragraph_end))
        return paragraphs

    def _split_long_text(self, original: str, start: int, end: int) -> list[tuple[int, int]]:
        words = [
            (start + match.start(), start + match.end())
            for match in WORD_RE.finditer(original[start:end])
        ]
        result: list[tuple[int, int]] = []
        chunk_start: int | None = None
        chunk_end: int | None = None
        for word_start, word_end in words:
            if chunk_start is None:
                chunk_start, chunk_end = word_start, word_end
            elif word_end - chunk_start <= self.max_chars:
                chunk_end = word_end
            else:
                result.append((chunk_start, chunk_end))
                chunk_start, chunk_end = word_start, word_end
        if chunk_start is not None and chunk_end is not None:
            result.append((chunk_start, chunk_end))
        return result

    @staticmethod
    def _chunk_id(revision_id: str, ordinal: int, text: str) -> str:
        value = f"{revision_id}\x00{ordinal}\x00{text}".encode()
        return sha256(value).hexdigest()

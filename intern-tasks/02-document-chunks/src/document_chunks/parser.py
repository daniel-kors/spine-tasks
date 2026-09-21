"""Document parser interface and typed input errors."""

from typing import Protocol

from .models import ParsedChunk, SourceDocument


class DocumentParseError(Exception):
    """Base error raised while reading or parsing a source document."""


class DocumentDecodeError(DocumentParseError):
    """The source document is not valid UTF-8."""


class EmptyDocumentError(DocumentParseError):
    """The source document contains no text chunks."""


class UnsupportedMediaTypeError(DocumentParseError):
    """No parser is available for the requested media type."""


class DocumentParser(Protocol):
    def parse(self, document: SourceDocument) -> tuple[ParsedChunk, ...]: ...

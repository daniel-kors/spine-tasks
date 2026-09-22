"""Pure validation rules; this module performs no I/O or model calls."""

import re
from collections import defaultdict

from .models import Claim, ContextReference, DraftAnswer, RetrievedChunk, ValidatedAnswer

NO_CONTEXT = "NO_CONTEXT"
UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
UNKNOWN_CITATION = "UNKNOWN_CITATION"
STALE_CITATION = "STALE_CITATION"
QUOTE_NOT_FOUND = "QUOTE_NOT_FOUND"
PARTIAL_COVERAGE = "PARTIAL_COVERAGE"


def validate_answer(
    draft: DraftAnswer,
    available: tuple[RetrievedChunk, ...],
) -> ValidatedAnswer:
    """Keep supported claims only and abstain when none remain."""
    if not available:
        return _abstain(NO_CONTEXT)

    by_id = {item.reference.chunk_id: item for item in available}
    stale_ids = _find_stale_chunk_ids(available)
    accepted: list[Claim] = []
    reasons: list[str] = []

    for claim in draft.claims:
        reason = _invalid_reason(claim, by_id, stale_ids)
        if reason is None:
            accepted.append(claim)
        else:
            _append_once(reasons, reason)

    if not accepted:
        if not draft.claims:
            _append_once(reasons, UNSUPPORTED_CLAIM)
        return _abstain(*reasons)

    if len(accepted) != len(draft.claims):
        reasons.insert(0, PARTIAL_COVERAGE)

    citations = _collect_citations(accepted, by_id)
    return ValidatedAnswer(
        status="answered",
        answer_text=" ".join(claim.text.strip() for claim in accepted),
        citations=citations,
        reasons=tuple(reasons),
    )


def _invalid_reason(
    claim: Claim,
    by_id: dict[str, RetrievedChunk],
    stale_ids: frozenset[str],
) -> str | None:
    if not claim.citation_ids:
        return UNSUPPORTED_CLAIM
    if any(chunk_id not in by_id for chunk_id in claim.citation_ids):
        return UNKNOWN_CITATION
    if any(chunk_id in stale_ids for chunk_id in claim.citation_ids):
        return STALE_CITATION
    cited = tuple(by_id[chunk_id] for chunk_id in claim.citation_ids)
    if not all(_contains_excerpt(chunk.text, claim.text) for chunk in cited):
        return QUOTE_NOT_FOUND
    return None


def _find_stale_chunk_ids(available: tuple[RetrievedChunk, ...]) -> frozenset[str]:
    by_source: dict[str, list[RetrievedChunk]] = defaultdict(list)
    for chunk in available:
        by_source[chunk.reference.source_id].append(chunk)

    stale: set[str] = set()
    for chunks in by_source.values():
        revision_ids = {chunk.reference.revision_id for chunk in chunks}
        if len(revision_ids) < 2:
            continue
        timestamps = [chunk.revision_observed_at for chunk in chunks]
        if any(timestamp is None for timestamp in timestamps):
            stale.update(chunk.reference.chunk_id for chunk in chunks)
            continue
        newest = max(timestamp for timestamp in timestamps if timestamp is not None)
        newest_revisions = {
            chunk.reference.revision_id
            for chunk in chunks
            if chunk.revision_observed_at == newest
        }
        if len(newest_revisions) != 1:
            stale.update(chunk.reference.chunk_id for chunk in chunks)
            continue
        stale.update(
            chunk.reference.chunk_id
            for chunk in chunks
            if chunk.revision_observed_at != newest
        )
    return frozenset(stale)


def _contains_excerpt(source_text: str, excerpt: str) -> bool:
    def normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    return normalize(excerpt) in normalize(source_text)


def _collect_citations(
    claims: list[Claim], by_id: dict[str, RetrievedChunk]
) -> tuple[ContextReference, ...]:
    seen: set[str] = set()
    references: list[ContextReference] = []
    for claim in claims:
        for chunk_id in claim.citation_ids:
            if chunk_id not in seen:
                references.append(by_id[chunk_id].reference)
                seen.add(chunk_id)
    return tuple(references)


def _abstain(*reasons: str) -> ValidatedAnswer:
    return ValidatedAnswer(
        status="abstained",
        answer_text=None,
        citations=(),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)

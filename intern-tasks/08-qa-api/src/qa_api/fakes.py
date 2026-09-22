"""Deterministic local components used by the runnable fake mode."""

from .models import (
    Claim,
    ContextReference,
    DraftAnswer,
    RetrievalResult,
    RetrievedChunk,
    Subject,
    ValidatedAnswer,
)


class FixtureGateway:
    def __init__(self, chunks_by_question: dict[str, tuple[RetrievedChunk, ...]]) -> None:
        self.chunks_by_question = chunks_by_question

    async def retrieve(self, subject: Subject, text: str) -> RetrievalResult:
        candidates = self.chunks_by_question.get(text, ())
        allowed = tuple(
            chunk
            for chunk in candidates
            if chunk.workspace_id == subject.workspace_id
            and chunk.required_scope in subject.scopes
        )
        return RetrievalResult(
            chunks=allowed,
            index_version="fake-index-v1",
            policy_version="fake-policy-v1",
        )


class FakeAnswerComposer:
    async def compose(
        self, question: str, chunks: tuple[RetrievedChunk, ...]
    ) -> DraftAnswer:
        del question
        return DraftAnswer(
            claims=tuple(
                Claim(text=chunk.text, citation_ids=(chunk.reference.chunk_id,))
                for chunk in chunks
            ),
            summary=" ".join(chunk.text for chunk in chunks),
        )


class StrictAnswerValidator:
    def validate(
        self, draft: DraftAnswer, available: tuple[RetrievedChunk, ...]
    ) -> ValidatedAnswer:
        by_id = {chunk.reference.chunk_id: chunk for chunk in available}
        if not available:
            return ValidatedAnswer(
                status="abstained",
                answer_text=None,
                citations=(),
                reasons=("NO_CONTEXT",),
            )
        references: list[ContextReference] = []
        accepted: list[str] = []
        for claim in draft.claims:
            if not claim.citation_ids:
                continue
            cited = [by_id.get(chunk_id) for chunk_id in claim.citation_ids]
            if any(chunk is None for chunk in cited):
                continue
            if not all(claim.text.casefold() in chunk.text.casefold() for chunk in cited if chunk):
                continue
            accepted.append(claim.text)
            references.extend(chunk.reference for chunk in cited if chunk is not None)
        if not accepted:
            return ValidatedAnswer(
                status="abstained",
                answer_text=None,
                citations=(),
                reasons=("UNSUPPORTED_ANSWER",),
            )
        unique = tuple({reference.chunk_id: reference for reference in references}.values())
        return ValidatedAnswer(
            status="answered",
            answer_text=" ".join(accepted),
            citations=unique,
            reasons=(),
        )

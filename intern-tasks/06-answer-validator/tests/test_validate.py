"""Required checks for the pure answer validator."""

from datetime import UTC, datetime
from typing import Any

from answer_validator.models import Claim, DraftAnswer
from answer_validator.validate import validate_answer


def draft(text: str, *citation_ids: str) -> DraftAnswer:
    return DraftAnswer(
        claims=(Claim(text=text, citation_ids=citation_ids),),
        summary=text,
    )


def test_empty_retrieval_causes_abstention() -> None:
    result = validate_answer(draft("Суточные составляют 1200 рублей", "c1"), available=())

    assert result.status == "abstained"
    assert result.answer_text is None
    assert result.citations == ()
    assert "NO_CONTEXT" in result.reasons


def test_unknown_citation_causes_abstention(chunk_factory: Any) -> None:
    result = validate_answer(
        draft("Суточные — 5000", "missing"),
        available=(chunk_factory(),),
    )

    assert result.status == "abstained"
    assert "UNKNOWN_CITATION" in result.reasons


def test_claim_with_two_valid_citations_is_accepted(chunk_factory: Any) -> None:
    first = chunk_factory(chunk_id="travel-c1")
    second = chunk_factory(
        chunk_id="finance-c1",
        source_id="finance-policy",
        revision_id="22222222-2222-4222-8222-222222222222",
    )

    result = validate_answer(
        draft("Суточные составляют 1200 рублей", "travel-c1", "finance-c1"),
        available=(first, second),
    )

    assert result.status == "answered"
    assert [reference.chunk_id for reference in result.citations] == [
        "travel-c1",
        "finance-c1",
    ]
    assert result.reasons == ()


def test_old_revision_is_marked_stale(chunk_factory: Any) -> None:
    old = chunk_factory(
        chunk_id="travel-v1",
        revision_id="11111111-1111-4111-8111-111111111111",
        text="Суточные составляют 900 рублей.",
        observed_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    current = chunk_factory(
        chunk_id="travel-v2",
        revision_id="11111111-1111-4111-8111-222222222222",
        observed_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    result = validate_answer(
        draft("Суточные составляют 900 рублей", "travel-v1"),
        available=(old, current),
    )

    assert result.status == "abstained"
    assert "STALE_CITATION" in result.reasons


def test_claim_without_citation_is_removed_from_partial_answer(chunk_factory: Any) -> None:
    answer = DraftAnswer(
        claims=(
            Claim(
                text="Суточные составляют 1200 рублей",
                citation_ids=("travel-v2-daily",),
            ),
            Claim(text="Гостиница стоит 50 000 рублей", citation_ids=()),
        ),
        summary="Суточные — 1200, гостиница — 50 000 рублей.",
    )

    result = validate_answer(answer, available=(chunk_factory(),))

    assert result.status == "answered"
    assert result.answer_text == "Суточные составляют 1200 рублей"
    assert "50 000" not in result.answer_text
    assert result.reasons == ("PARTIAL_COVERAGE", "UNSUPPORTED_CLAIM")


def test_claim_not_present_in_cited_chunk_is_rejected(chunk_factory: Any) -> None:
    result = validate_answer(
        draft("Суточные составляют 5000 рублей", "travel-v2-daily"),
        available=(chunk_factory(),),
    )

    assert result.status == "abstained"
    assert "QUOTE_NOT_FOUND" in result.reasons

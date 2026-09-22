"""Required authorization scenarios for the central gateway."""

from typing import Any

import pytest

from access_gateway.audit import InMemoryAuditSink
from access_gateway.gateway import AuthorizedRetriever
from access_gateway.leaky_retriever import LeakyRetriever
from access_gateway.models import RetrievalQuery, RetrievalResult, Subject
from access_gateway.policy import GroupAccessPolicy


def gateway_for(*chunks: Any) -> tuple[AuthorizedRetriever, InMemoryAuditSink]:
    audit = InMemoryAuditSink()
    gateway = AuthorizedRetriever(
        LeakyRetriever(tuple(chunks)),
        GroupAccessPolicy(),
        audit,
    )
    return gateway, audit


@pytest.mark.asyncio
async def test_all_employees_user_cannot_read_engineering(chunk_factory: Any) -> None:
    gateway, audit = gateway_for(chunk_factory())

    result = await gateway.retrieve(
        Subject(user_id="employee-1", workspace_id="alpha", scopes={"all-employees"}),
        "Какое кодовое имя прототипа?",
    )

    assert result.chunks == ()
    assert result.policy_version == "access-policy-v1"
    assert audit.events[0].reason_code == "REQUIRED_SCOPE_MISSING"


@pytest.mark.asyncio
async def test_engineer_can_read_employee_and_engineering_groups(chunk_factory: Any) -> None:
    employee_chunk = chunk_factory(
        chunk_id="travel-daily",
        source_id="travel-policy",
        required_scope="all-employees",
        text="Суточные составляют 1200 рублей.",
    )
    engineering_chunk = chunk_factory()
    gateway, audit = gateway_for(employee_chunk, engineering_chunk)

    result = await gateway.retrieve(
        Subject(user_id="engineer-1", workspace_id="alpha", scopes={"engineering"}),
        "Покажи доступные правила",
    )

    assert [chunk.reference.chunk_id for chunk in result.chunks] == [
        "travel-daily",
        "engineering-name",
    ]
    assert audit.events == []


@pytest.mark.asyncio
async def test_beta_user_cannot_read_alpha_chunk(chunk_factory: Any) -> None:
    gateway, audit = gateway_for(chunk_factory(required_scope="all-employees"))

    result = await gateway.retrieve(
        Subject(user_id="beta-user", workspace_id="beta", scopes={"all-employees"}),
        "Правила",
    )

    assert result.chunks == ()
    assert audit.events[0].reason_code == "WORKSPACE_MISMATCH"


@pytest.mark.asyncio
async def test_leaky_retriever_does_not_cause_data_leak(chunk_factory: Any) -> None:
    leaked = chunk_factory(text="Закрытый секретный текст")
    gateway, _ = gateway_for(leaked)

    result = await gateway.retrieve(
        Subject(user_id="employee-1", workspace_id="alpha", scopes={"all-employees"}),
        "Верни секрет",
    )

    serialized = result.model_dump_json()
    assert result.chunks == ()
    assert "Закрытый секретный текст" not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject", "expected_reason"),
    [
        (
            Subject(user_id="", workspace_id="alpha", scopes={"all-employees"}),
            "USER_MISSING",
        ),
        (
            Subject(user_id="employee-1", workspace_id="alpha", scopes=set()),
            "SCOPES_MISSING",
        ),
        (
            Subject(user_id="employee-1", workspace_id="alpha", scopes={"unknown"}),
            "REQUIRED_SCOPE_MISSING",
        ),
    ],
)
async def test_missing_identity_or_known_group_never_grants_full_access(
    subject: Subject,
    expected_reason: str,
    chunk_factory: Any,
) -> None:
    gateway, audit = gateway_for(chunk_factory(required_scope="all-employees"))

    result = await gateway.retrieve(subject, "Правила")

    assert result.chunks == ()
    assert audit.events[0].reason_code == expected_reason


@pytest.mark.asyncio
async def test_gateway_builds_query_from_subject(chunk_factory: Any) -> None:
    class RecordingRetriever:
        def __init__(self) -> None:
            self.query: RetrievalQuery | None = None

        async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
            self.query = query
            return RetrievalResult(chunks=(), strategy="recording", index_version="v1")

    inner = RecordingRetriever()
    subject = Subject(user_id="u-7", workspace_id="alpha", scopes={"engineering"})
    gateway = AuthorizedRetriever(inner, GroupAccessPolicy("policy-7"), InMemoryAuditSink())

    result = await gateway.retrieve(subject, "Вопрос")

    assert inner.query == RetrievalQuery(
        workspace_id="alpha",
        user_id="u-7",
        scopes={"engineering"},
        text="Вопрос",
    )
    assert result.policy_version == "policy-7"

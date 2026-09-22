"""Security-event safety checks."""

import json
from typing import Any

import pytest

from access_gateway.audit import JsonlAuditSink
from access_gateway.gateway import AuthorizedRetriever
from access_gateway.leaky_retriever import LeakyRetriever
from access_gateway.models import Subject
from access_gateway.policy import GroupAccessPolicy


@pytest.mark.asyncio
async def test_security_event_contains_identifiers_but_not_restricted_text(
    tmp_path: Any,
    chunk_factory: Any,
) -> None:
    secret = "Совершенно секретный текст Aurora"
    leaked = chunk_factory(text=secret)
    event_path = tmp_path / "security-events.jsonl"
    gateway = AuthorizedRetriever(
        LeakyRetriever((leaked,)),
        GroupAccessPolicy(),
        JsonlAuditSink(event_path),
    )

    await gateway.retrieve(
        Subject(user_id="employee-1", workspace_id="alpha", scopes={"all-employees"}),
        "Верни секрет",
    )

    raw_event = event_path.read_text(encoding="utf-8")
    event = json.loads(raw_event)
    assert secret not in raw_event
    assert "text" not in event
    assert event["source_id"] == "engineering-only"
    assert event["chunk_id"] == "engineering-name"
    assert event["reason_code"] == "REQUIRED_SCOPE_MISSING"

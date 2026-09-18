"""Tests for the JSONL storage boundary."""

from pathlib import Path

import pytest

from source_revisions.repository import JsonlRevisionRepository
from source_revisions.service import RevisionService


def test_jsonl_store_persists_revisions_without_duplicate_lines(tmp_path: Path) -> None:
    document = tmp_path / "policy.md"
    document.write_text("Версия 1", encoding="utf-8")
    store = tmp_path / "revisions.jsonl"
    service = RevisionService(JsonlRevisionRepository(store))

    first = service.register_file("alpha", "policy", document, "text/markdown")
    repeated = service.register_file("alpha", "policy", document, "text/markdown")
    document.write_text("Версия 2", encoding="utf-8")
    second = service.register_file("alpha", "policy", document, "text/markdown")

    reopened = JsonlRevisionRepository(store)
    assert repeated.status == "unchanged"
    assert len(store.read_text(encoding="utf-8").splitlines()) == 2
    assert [item.revision_id for item in reopened.history("alpha", "policy")] == [
        first.revision.revision_id,
        second.revision.revision_id,
    ]
    assert reopened.history("beta", "policy") == []


def test_jsonl_store_retains_tombstone_after_reopening(tmp_path: Path) -> None:
    document = tmp_path / "policy.md"
    document.write_text("Правило", encoding="utf-8")
    store = tmp_path / "revisions.jsonl"
    service = RevisionService(JsonlRevisionRepository(store))

    original = service.register_file("alpha", "policy", document, "text/markdown")
    deleted = service.tombstone("alpha", "policy")

    history = JsonlRevisionRepository(store).history("alpha", "policy")
    assert [item.revision_id for item in history] == [
        original.revision.revision_id,
        deleted.revision.revision_id,
    ]
    assert not history[0].is_tombstone
    assert history[1].is_tombstone


def test_malformed_jsonl_reports_line_number(tmp_path: Path) -> None:
    document = tmp_path / "policy.md"
    document.write_text("Правило", encoding="utf-8")
    store = tmp_path / "revisions.jsonl"
    RevisionService(JsonlRevisionRepository(store)).register_file(
        "alpha", "policy", document, "text/markdown"
    )
    with store.open("a", encoding="utf-8") as stream:
        stream.write("{not valid json}\n")

    with pytest.raises(ValueError, match=r"line 2"):
        JsonlRevisionRepository(store).history("alpha", "policy")

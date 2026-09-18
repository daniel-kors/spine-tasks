"""Tests for revision registration rules and immutable contracts."""

from datetime import UTC
from pathlib import Path

import pytest
from pydantic import ValidationError

from source_revisions.checksum import file_sha256
from source_revisions.repository import InMemoryRevisionRepository
from source_revisions.service import RevisionService


def test_file_sha256_uses_file_contents(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Правило", encoding="utf-8")

    first = file_sha256(path)
    path.write_text("Правила", encoding="utf-8")

    assert len(first) == 64
    assert file_sha256(path) != first


def test_same_content_is_registered_once(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Правило", encoding="utf-8")
    repository = InMemoryRevisionRepository()
    service = RevisionService(repository)

    first = service.register_file("alpha", "policy", path, "text/markdown")
    second = service.register_file("alpha", "policy", path, "text/markdown")

    assert first.status == "created"
    assert second.status == "unchanged"
    assert second.revision.revision_id == first.revision.revision_id
    assert len(repository.history("alpha", "policy")) == 1


def test_one_character_change_creates_second_revision(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Правило", encoding="utf-8")
    repository = InMemoryRevisionRepository()
    service = RevisionService(repository)

    first = service.register_file("alpha", "policy", path, "text/markdown")
    path.write_text("Правила", encoding="utf-8")
    second = service.register_file("alpha", "policy", path, "text/markdown")

    history = repository.history("alpha", "policy")
    assert second.status == "created"
    assert second.revision.revision_id != first.revision.revision_id
    assert second.revision.checksum_sha256 != first.revision.checksum_sha256
    assert [item.revision_id for item in history] == [
        first.revision.revision_id,
        second.revision.revision_id,
    ]


def test_same_source_id_has_separate_workspace_histories(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Правило", encoding="utf-8")
    repository = InMemoryRevisionRepository()
    service = RevisionService(repository)

    alpha = service.register_file("alpha", "policy", path, "text/markdown")
    beta = service.register_file("beta", "policy", path, "text/markdown")

    assert alpha.status == beta.status == "created"
    assert alpha.revision.revision_id != beta.revision.revision_id
    assert repository.history("alpha", "policy") == [alpha.revision]
    assert repository.history("beta", "policy") == [beta.revision]


def test_tombstone_keeps_previous_revisions_and_is_repeatable(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Версия 1", encoding="utf-8")
    repository = InMemoryRevisionRepository()
    service = RevisionService(repository)

    first = service.register_file("alpha", "policy", path, "text/markdown")
    path.write_text("Версия 2", encoding="utf-8")
    second = service.register_file("alpha", "policy", path, "text/markdown")
    deleted = service.tombstone("alpha", "policy")
    repeated = service.tombstone("alpha", "policy")

    history = repository.history("alpha", "policy")
    assert deleted.status == "created"
    assert deleted.revision.is_tombstone
    assert repeated.status == "unchanged"
    assert repeated.revision.revision_id == deleted.revision.revision_id
    assert [item.revision_id for item in history] == [
        first.revision.revision_id,
        second.revision.revision_id,
        deleted.revision.revision_id,
    ]


def test_revision_is_frozen_and_timestamp_is_utc(tmp_path: Path) -> None:
    path = tmp_path / "policy.md"
    path.write_text("Правило", encoding="utf-8")
    revision = RevisionService(InMemoryRevisionRepository()).register_file(
        "alpha", "policy", path, "text/markdown"
    ).revision

    assert revision.observed_at.tzinfo is UTC
    with pytest.raises(ValidationError):
        revision.source_id = "changed"

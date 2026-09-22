"""Default-deny group access policy."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from .models import AccessDecision, RetrievedChunk, Subject


class AccessPolicy(Protocol):
    version: str

    def can_read(self, subject: Subject, chunk: RetrievedChunk) -> AccessDecision: ...


class GroupAccessPolicy:
    def __init__(
        self,
        version: str = "access-policy-v1",
        grants: Mapping[str, frozenset[str]] | None = None,
    ) -> None:
        self.version = version
        configured = grants or {
            "all-employees": frozenset({"all-employees"}),
            "engineering": frozenset({"all-employees", "engineering"}),
        }
        self.grants = MappingProxyType(dict(configured))

    def can_read(self, subject: Subject, chunk: RetrievedChunk) -> AccessDecision:
        reason = self._denial_reason(subject, chunk)
        if reason is not None:
            return self._decision(False, reason)
        effective_scopes = frozenset(
            granted
            for assigned in subject.scopes
            for granted in self.grants.get(assigned, frozenset())
        )
        if chunk.required_scope not in effective_scopes:
            return self._decision(False, "REQUIRED_SCOPE_MISSING")
        return self._decision(True, "ACCESS_GRANTED")

    def _denial_reason(self, subject: Subject, chunk: RetrievedChunk) -> str | None:
        if not subject.user_id.strip():
            return "USER_MISSING"
        if not subject.scopes:
            return "SCOPES_MISSING"
        if subject.workspace_id != chunk.workspace_id:
            return "WORKSPACE_MISMATCH"
        if not chunk.required_scope.strip():
            return "RESOURCE_SCOPE_MISSING"
        return None

    def _decision(self, allowed: bool, reason_code: str) -> AccessDecision:
        return AccessDecision(
            allowed=allowed,
            reason_code=reason_code,
            policy_version=self.version,
        )

"""Central access check around any context retriever."""

from datetime import UTC, datetime

from .audit import AuditSink
from .models import (
    AccessDecision,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
    SecurityEvent,
    Subject,
)
from .policy import AccessPolicy
from .retriever import Retriever


class AuthorizedRetriever:
    def __init__(self, inner: Retriever, policy: AccessPolicy, audit: AuditSink) -> None:
        self.inner = inner
        self.policy = policy
        self.audit = audit

    async def retrieve(self, subject: Subject, text: str) -> RetrievalResult:
        query = RetrievalQuery(
            workspace_id=subject.workspace_id,
            user_id=subject.user_id,
            scopes=subject.scopes,
            text=text,
        )
        raw = await self.inner.retrieve(query)
        allowed: list[RetrievedChunk] = []
        for chunk in raw.chunks:
            decision = self._decide(subject, chunk)
            if decision.allowed:
                allowed.append(chunk)
            else:
                self.audit.record(self._denied_event(subject, chunk, decision))
        return raw.model_copy(
            update={"chunks": tuple(allowed), "policy_version": self.policy.version}
        )

    def _decide(self, subject: Subject, chunk: RetrievedChunk) -> AccessDecision:
        try:
            return self.policy.can_read(subject, chunk)
        except Exception:
            return AccessDecision(
                allowed=False,
                reason_code="POLICY_ERROR",
                policy_version=self.policy.version,
            )

    @staticmethod
    def _denied_event(
        subject: Subject,
        chunk: RetrievedChunk,
        decision: AccessDecision,
    ) -> SecurityEvent:
        return SecurityEvent(
            occurred_at=datetime.now(UTC),
            user_id=subject.user_id,
            subject_workspace_id=subject.workspace_id,
            chunk_workspace_id=chunk.workspace_id,
            source_id=chunk.reference.source_id,
            revision_id=chunk.reference.revision_id,
            chunk_id=chunk.reference.chunk_id,
            required_scope=chunk.required_scope,
            reason_code=decision.reason_code,
            policy_version=decision.policy_version,
        )

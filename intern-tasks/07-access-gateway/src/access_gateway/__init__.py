"""Central authorization gateway for knowledge retrieval."""

from .audit import AuditSink, InMemoryAuditSink, JsonlAuditSink
from .gateway import AuthorizedRetriever
from .leaky_retriever import LeakyRetriever
from .models import (
    AccessDecision,
    ContextReference,
    RetrievalQuery,
    RetrievalResult,
    RetrievedChunk,
    SecurityEvent,
    Subject,
)
from .policy import GroupAccessPolicy
from .retriever import Retriever

__all__ = [
    "AccessDecision",
    "AuditSink",
    "AuthorizedRetriever",
    "ContextReference",
    "GroupAccessPolicy",
    "InMemoryAuditSink",
    "JsonlAuditSink",
    "LeakyRetriever",
    "RetrievedChunk",
    "RetrievalQuery",
    "RetrievalResult",
    "Retriever",
    "SecurityEvent",
    "Subject",
]

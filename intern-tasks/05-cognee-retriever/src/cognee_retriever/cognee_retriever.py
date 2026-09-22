"""Map normalized Cognee chunks to the application retrieval contract."""

from typing import Any

from .cognee_client import CogneeClient, decode_envelope
from .models import ContextReference, RetrievalQuery, RetrievalResult, RetrievedChunk
from .projections import ProjectionStore


class CogneeRetriever:
    def __init__(self, client: CogneeClient, projection_store: ProjectionStore) -> None:
        self.client = client
        self.projection_store = projection_store

    async def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        await self.projection_store.initialize()
        projection = await self.projection_store.get_active(query.workspace_id)
        if projection is None:
            raise RuntimeError(f"No active projection for workspace {query.workspace_id!r}")
        payloads = await self.client.recall(query.text, projection.dataset_name)
        chunks: list[RetrievedChunk] = []
        for payload in payloads:
            normalized = extract_context_payload(payload)
            metadata = normalized["metadata"]
            if metadata.get("workspace_id") != query.workspace_id:
                continue
            required_scope = str(metadata.get("required_scope", ""))
            if required_scope not in query.scopes:
                continue
            chunks.append(
                RetrievedChunk(
                    workspace_id=query.workspace_id,
                    required_scope=required_scope,
                    text=str(normalized["text"]),
                    reference=ContextReference(
                        source_id=metadata["source_id"],
                        revision_id=metadata["revision_id"],
                        chunk_id=metadata.get("chunk_id", normalized.get("id", "")),
                        locator=metadata["locator"],
                    ),
                )
            )
        return RetrievalResult(
            chunks=tuple(chunks),
            strategy="cognee-chunks",
            index_version=str(projection.projection_id),
        )


def extract_context_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    text = payload.get("text") or payload.get("content")
    if isinstance(metadata, dict) and text is not None:
        return {"id": payload.get("id", ""), "text": text, "metadata": metadata}
    if isinstance(text, str) and text.startswith("SPINE_CONTEXT_V1:"):
        return decode_envelope(text)
    nested = payload.get("search_result") or payload.get("result")
    if isinstance(nested, dict):
        return extract_context_payload(nested)
    if isinstance(nested, str) and nested.startswith("SPINE_CONTEXT_V1:"):
        return decode_envelope(nested)
    raise ValueError("Cognee chunk does not contain restorable source metadata")

"""Small client boundary around Cognee and an offline configured fake."""

import json
from pathlib import Path
from typing import Any, Protocol

from .local_paths import configure_cognee_paths


class CogneeClient(Protocol):
    async def remember(self, texts: list[str], dataset_name: str) -> None: ...

    async def recall(self, query: str, dataset_name: str) -> list[dict[str, Any]]: ...


class RealCogneeClient:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    @staticmethod
    def _module(project_root: Path) -> Any:
        configure_cognee_paths(project_root)
        import cognee

        return cognee

    async def remember(self, texts: list[str], dataset_name: str) -> None:
        cognee = self._module(self.project_root)
        await cognee.remember(texts, dataset_name=dataset_name, self_improvement=False)

    async def recall(self, query: str, dataset_name: str) -> list[dict[str, Any]]:
        cognee = self._module(self.project_root)
        results = await cognee.recall(
            query_text=query,
            query_type=cognee.SearchType.CHUNKS,
            datasets=[dataset_name],
            auto_route=False,
        )
        return [normalize_cognee_item(item) for item in results]


class ConfiguredFakeCogneeClient:
    def __init__(self, storage: Path, configured_results: Path) -> None:
        self.storage = storage
        self.configured_results = configured_results

    async def remember(self, texts: list[str], dataset_name: str) -> None:
        self.storage.mkdir(parents=True, exist_ok=True)
        path = self.storage / f"{dataset_name}.json"
        path.write_text(json.dumps(texts, ensure_ascii=False, indent=2), encoding="utf-8")

    async def recall(self, query: str, dataset_name: str) -> list[dict[str, Any]]:
        dataset_path = self.storage / f"{dataset_name}.json"
        if not dataset_path.exists():
            raise FileNotFoundError(f"Fake dataset does not exist: {dataset_name}")
        stored_texts = json.loads(dataset_path.read_text(encoding="utf-8"))
        if query.startswith("__verify_projection__:"):
            return [decode_envelope(stored_texts[0])] if stored_texts else []
        configured = json.loads(self.configured_results.read_text(encoding="utf-8"))
        if query in configured.get("errors", {}):
            raise RuntimeError(configured["errors"][query])
        stored_chunks = [decode_envelope(value) for value in stored_texts]
        results: list[dict[str, Any]] = []
        for expected in configured.get("answers", {}).get(query, []):
            reference = expected["reference"]
            match = next(
                (
                    chunk
                    for chunk in stored_chunks
                    if chunk["metadata"].get("source_id") == reference["source_id"]
                    and chunk["metadata"].get("revision_id") == reference["revision_id"]
                    and expected["text"] in chunk["text"]
                ),
                None,
            )
            if match is not None:
                results.append(match)
        return results


def normalize_cognee_item(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "__dict__"):
        return dict(vars(item))
    raise TypeError(f"Unsupported Cognee result type: {type(item).__name__}")


def decode_envelope(value: str) -> dict[str, Any]:
    prefix = "SPINE_CONTEXT_V1:"
    if not value.startswith(prefix):
        return {"id": "unknown", "text": value, "metadata": {}}
    metadata_line, text = value[len(prefix) :].split("\n", maxsplit=1)
    metadata = json.loads(metadata_line)
    return {"id": metadata["chunk_id"], "text": text, "metadata": metadata}

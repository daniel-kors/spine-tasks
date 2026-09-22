"""Projection lifecycle and atomic active-version storage."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import aiosqlite

from .cognee_client import CogneeClient
from .models import ManifestChunk, ProjectionVersion


class ProjectionStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as database:
            await database.executescript(
                """
                CREATE TABLE IF NOT EXISTS projection_versions (
                    projection_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    projection_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS active_projections (
                    workspace_id TEXT PRIMARY KEY,
                    projection_id TEXT NOT NULL,
                    FOREIGN KEY (projection_id) REFERENCES projection_versions(projection_id)
                );
                """
            )
            await database.commit()

    async def save(self, projection: ProjectionVersion) -> None:
        async with aiosqlite.connect(self.path) as database:
            await database.execute(
                """
                INSERT OR REPLACE INTO projection_versions
                    (projection_id, workspace_id, projection_json)
                VALUES (?, ?, ?)
                """,
                (
                    str(projection.projection_id),
                    projection.workspace_id,
                    projection.model_dump_json(),
                ),
            )
            await database.commit()

    async def get(self, projection_id: UUID) -> ProjectionVersion | None:
        async with aiosqlite.connect(self.path) as database:
            cursor = await database.execute(
                "SELECT projection_json FROM projection_versions WHERE projection_id = ?",
                (str(projection_id),),
            )
            row = await cursor.fetchone()
        return ProjectionVersion.model_validate_json(row[0]) if row else None

    async def get_active(self, workspace_id: str) -> ProjectionVersion | None:
        async with aiosqlite.connect(self.path) as database:
            cursor = await database.execute(
                """
                SELECT versions.projection_json
                FROM active_projections AS active
                JOIN projection_versions AS versions
                    ON versions.projection_id = active.projection_id
                WHERE active.workspace_id = ?
                """,
                (workspace_id,),
            )
            row = await cursor.fetchone()
        return ProjectionVersion.model_validate_json(row[0]) if row else None

    async def activate(self, projection_id: UUID) -> ProjectionVersion:
        projection = await self.get(projection_id)
        if projection is None:
            raise ValueError(f"Unknown projection: {projection_id}")
        if projection.state not in {"ready", "active"}:
            raise ValueError(f"Projection is not ready: {projection.state}")

        async with aiosqlite.connect(self.path) as database:
            await database.execute("BEGIN IMMEDIATE")
            try:
                cursor = await database.execute(
                    "SELECT projection_id FROM active_projections WHERE workspace_id = ?",
                    (projection.workspace_id,),
                )
                previous = await cursor.fetchone()
                if previous and previous[0] != str(projection_id):
                    await self._replace_state(database, UUID(previous[0]), "superseded")
                active = projection.model_copy(update={"state": "active"})
                await database.execute(
                    "UPDATE projection_versions SET projection_json = ? WHERE projection_id = ?",
                    (active.model_dump_json(), str(projection_id)),
                )
                await database.execute(
                    """
                    INSERT INTO active_projections (workspace_id, projection_id)
                    VALUES (?, ?)
                    ON CONFLICT(workspace_id) DO UPDATE SET projection_id = excluded.projection_id
                    """,
                    (projection.workspace_id, str(projection_id)),
                )
                await database.commit()
            except Exception:
                await database.rollback()
                raise
        return active

    async def _replace_state(
        self, database: aiosqlite.Connection, projection_id: UUID, state: str
    ) -> None:
        cursor = await database.execute(
            "SELECT projection_json FROM projection_versions WHERE projection_id = ?",
            (str(projection_id),),
        )
        row = await cursor.fetchone()
        if row:
            previous = ProjectionVersion.model_validate_json(row[0])
            updated = previous.model_copy(update={"state": state})
            await database.execute(
                "UPDATE projection_versions SET projection_json = ? WHERE projection_id = ?",
                (updated.model_dump_json(), str(projection_id)),
            )


class ProjectionBuilder:
    def __init__(self, client: CogneeClient, store: ProjectionStore) -> None:
        self.client = client
        self.store = store

    async def build(
        self, workspace_id: str, manifest_directory: Path, *, activate: bool = True
    ) -> ProjectionVersion:
        await self.store.initialize()
        chunks = read_manifests(manifest_directory, workspace_id)
        projection_id = uuid4()
        dataset_name = f"{workspace_id}_projection_{projection_id.hex}"
        revisions = tuple(sorted({chunk.reference.revision_id for chunk in chunks}, key=str))
        projection = ProjectionVersion(
            projection_id=projection_id,
            workspace_id=workspace_id,
            dataset_name=dataset_name,
            source_revision_ids=revisions,
            state="building",
            created_at=datetime.now(UTC),
        )
        await self.store.save(projection)
        try:
            await self.client.remember([encode_chunk(chunk) for chunk in chunks], dataset_name)
            verification = await self.client.recall(
                f"__verify_projection__: {chunks[0].text[:120]}", dataset_name
            )
            if not verification:
                raise RuntimeError("Projection verification returned no chunks")
            projection = projection.model_copy(update={"state": "ready"})
            await self.store.save(projection)
            if activate:
                projection = await self.store.activate(projection_id)
            return projection
        except Exception as exc:
            failed = projection.model_copy(
                update={"state": "failed", "error_description": type(exc).__name__}
            )
            await self.store.save(failed)
            raise


def read_manifests(directory: Path, workspace_id: str) -> tuple[ManifestChunk, ...]:
    chunks: list[ManifestChunk] = []
    for path in sorted(directory.glob("*.jsonl"), key=lambda item: item.name):
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    chunk = ManifestChunk.model_validate_json(line)
                except ValueError as exc:
                    raise ValueError(f"Invalid manifest {path}, line {line_number}: {exc}") from exc
                if chunk.workspace_id == workspace_id:
                    chunks.append(chunk)
    if not chunks:
        raise ValueError(f"No manifest chunks for workspace {workspace_id!r}")
    return tuple(chunks)


def encode_chunk(chunk: ManifestChunk) -> str:
    metadata = {
        "workspace_id": chunk.workspace_id,
        "required_scope": chunk.required_scope,
        **chunk.reference.model_dump(mode="json"),
    }
    return f"SPINE_CONTEXT_V1:{json.dumps(metadata, ensure_ascii=False)}\n{chunk.text}"

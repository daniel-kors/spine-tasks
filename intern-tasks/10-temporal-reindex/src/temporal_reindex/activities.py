"""Temporal activities around an ordinary idempotent projection service."""

from typing import Protocol

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .models import IndexBatchInput, MarkFailedInput, ProjectionInput, ValidateManifestsInput


class ProjectionService(Protocol):
    async def validate(self, data: ValidateManifestsInput) -> None: ...

    async def create(self, data: ProjectionInput) -> None: ...

    async def index(self, data: IndexBatchInput) -> int: ...

    async def verify(self, data: ProjectionInput) -> None: ...

    async def activate(self, data: ProjectionInput) -> None: ...

    async def mark_failed(self, data: MarkFailedInput) -> None: ...


class ReindexActivities:
    def __init__(self, service: ProjectionService) -> None:
        self.service = service

    @activity.defn(name="validate_manifests")
    async def validate_manifests(self, data: ValidateManifestsInput) -> None:
        try:
            await self.service.validate(data)
        except ValueError as exc:
            raise ApplicationError(
                str(exc),
                type="ManifestValidationError",
                non_retryable=True,
            ) from exc

    @activity.defn(name="create_projection")
    async def create_projection(self, data: ProjectionInput) -> None:
        await self.service.create(data)

    @activity.defn(name="index_batch")
    async def index_batch(self, data: IndexBatchInput) -> int:
        return await self.service.index(data)

    @activity.defn(name="verify_projection")
    async def verify_projection(self, data: ProjectionInput) -> None:
        await self.service.verify(data)

    @activity.defn(name="activate_projection")
    async def activate_projection(self, data: ProjectionInput) -> None:
        await self.service.activate(data)

    @activity.defn(name="mark_failed")
    async def mark_failed(self, data: MarkFailedInput) -> None:
        await self.service.mark_failed(data)

    def registered(self) -> list[object]:
        return [
            self.validate_manifests,
            self.create_projection,
            self.index_batch,
            self.verify_projection,
            self.activate_projection,
            self.mark_failed,
        ]

"""Controllable application services for Temporal workflow tests."""

import asyncio
import os
import sys
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment

from temporal_reindex.models import (
    IndexBatchInput,
    MarkFailedInput,
    ProjectionInput,
    ValidateManifestsInput,
)
from temporal_reindex.service import InMemoryProjectionService


def reindex_input(count: int = 25):
    from temporal_reindex.models import ReindexInput

    return ReindexInput(
        workspace_id="alpha",
        projection_id="projection-test",
        manifest_paths=tuple(f"manifests/chunk-{number:03d}.jsonl" for number in range(count)),
    )


def uses_time_skipping() -> bool:
    default = "local" if sys.platform == "win32" else "time-skipping"
    return os.getenv("TEMPORAL_TEST_MODE", default) == "time-skipping"


@asynccontextmanager
async def workflow_environment() -> AsyncIterator[WorkflowEnvironment]:
    if uses_time_skipping():
        environment = await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter
        )
    else:
        environment = await WorkflowEnvironment.start_local(
            data_converter=pydantic_data_converter
        )
    async with environment:
        yield environment


class RecordingService(InMemoryProjectionService):
    def __init__(self) -> None:
        super().__init__()
        self.validation_calls = 0
        self.index_attempts: Counter[int] = Counter()
        self.activation_calls = 0
        self.mark_failed_calls = 0

    async def validate(self, data: ValidateManifestsInput) -> None:
        self.validation_calls += 1
        await super().validate(data)

    async def index(self, data: IndexBatchInput) -> int:
        self.index_attempts[data.batch_number] += 1
        return await super().index(data)

    async def activate(self, data: ProjectionInput) -> None:
        self.activation_calls += 1
        await super().activate(data)

    async def mark_failed(self, data: MarkFailedInput) -> None:
        self.mark_failed_calls += 1
        await super().mark_failed(data)


class TransientThirdBatchService(RecordingService):
    async def index(self, data: IndexBatchInput) -> int:
        self.index_attempts[data.batch_number] += 1
        if data.batch_number == 2 and self.index_attempts[data.batch_number] <= 2:
            raise RuntimeError("synthetic transient failure")
        return await InMemoryProjectionService.index(self, data)


class InvalidManifestService(RecordingService):
    async def validate(self, data: ValidateManifestsInput) -> None:
        del data
        self.validation_calls += 1
        raise ValueError("synthetic invalid manifest")


class FirstBatchGateService(RecordingService):
    def __init__(self) -> None:
        super().__init__()
        self.first_batch_indexed = asyncio.Event()
        self.release_first_batch = asyncio.Event()

    async def index(self, data: IndexBatchInput) -> int:
        count = await super().index(data)
        if data.batch_number == 0:
            self.first_batch_indexed.set()
            await self.release_first_batch.wait()
        return count


class ProgressGateService(RecordingService):
    def __init__(self) -> None:
        super().__init__()
        self.batch_entered = [asyncio.Event() for _ in range(3)]
        self.release_batch = [asyncio.Event() for _ in range(3)]
        self.verify_entered = asyncio.Event()
        self.release_verify = asyncio.Event()

    async def index(self, data: IndexBatchInput) -> int:
        count = await super().index(data)
        self.batch_entered[data.batch_number].set()
        await self.release_batch[data.batch_number].wait()
        return count

    async def verify(self, data: ProjectionInput) -> None:
        self.verify_entered.set()
        await self.release_verify.wait()
        await super().verify(data)

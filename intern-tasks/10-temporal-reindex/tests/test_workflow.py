"""Connected workflow checks using Temporal's time-skipping server."""

from time import perf_counter
from uuid import uuid4

import pytest
from temporalio.worker import Worker

from temporal_reindex.activities import ReindexActivities
from temporal_reindex.workflow import ReindexWorkflow

from .helpers import (
    FirstBatchGateService,
    InvalidManifestService,
    ProgressGateService,
    RecordingService,
    TransientThirdBatchService,
    reindex_input,
    uses_time_skipping,
    workflow_environment,
)

pytestmark = pytest.mark.integration


async def run_workflow(service: RecordingService):
    async with workflow_environment() as environment:
        activities = ReindexActivities(service)
        task_queue = f"test-{uuid4()}"
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[ReindexWorkflow],
            activities=activities.registered(),
        ):
            return await environment.client.execute_workflow(
                ReindexWorkflow.run,
                reindex_input(),
                id=f"workflow-{uuid4()}",
                task_queue=task_queue,
            )


@pytest.mark.asyncio
async def test_successful_workflow_activates_exactly_once() -> None:
    service = RecordingService()

    result = await run_workflow(service)

    assert result.status == "activated"
    assert result.indexed_count == 25
    assert service.activation_calls == 1
    assert service.index_attempts == {0: 1, 1: 1, 2: 1}


@pytest.mark.asyncio
async def test_third_batch_fails_twice_then_succeeds() -> None:
    service = TransientThirdBatchService()
    started = perf_counter()

    result = await run_workflow(service)
    elapsed = perf_counter() - started

    assert result.status == "activated"
    assert service.index_attempts == {0: 1, 1: 1, 2: 3}
    assert len(service.projections[("alpha", "projection-test")].indexed_by_key) == 3
    assert service.activation_calls == 1
    if uses_time_skipping():
        assert elapsed < 2.5
    else:
        assert elapsed < 8


@pytest.mark.asyncio
async def test_manifest_validation_error_is_not_retried() -> None:
    service = InvalidManifestService()

    result = await run_workflow(service)

    assert result.status == "failed"
    assert result.indexed_count == 0
    assert service.validation_calls == 1
    assert service.mark_failed_calls == 1
    assert service.activation_calls == 0


@pytest.mark.asyncio
async def test_cancel_after_first_batch_does_not_activate() -> None:
    service = FirstBatchGateService()
    async with workflow_environment() as environment:
        activities = ReindexActivities(service)
        task_queue = f"cancel-{uuid4()}"
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[ReindexWorkflow],
            activities=activities.registered(),
        ):
            handle = await environment.client.start_workflow(
                ReindexWorkflow.run,
                reindex_input(),
                id=f"workflow-{uuid4()}",
                task_queue=task_queue,
            )
            await service.first_batch_indexed.wait()
            await handle.signal(ReindexWorkflow.request_cancel)
            service.release_first_batch.set()
            result = await handle.result()

    assert result.status == "cancelled"
    assert result.indexed_count == 10
    assert service.activation_calls == 0
    assert service.index_attempts == {0: 1}


@pytest.mark.asyncio
async def test_progress_query_only_moves_forward() -> None:
    service = ProgressGateService()
    observed: list[int] = []
    async with workflow_environment() as environment:
        activities = ReindexActivities(service)
        task_queue = f"progress-{uuid4()}"
        async with Worker(
            environment.client,
            task_queue=task_queue,
            workflows=[ReindexWorkflow],
            activities=activities.registered(),
        ):
            handle = await environment.client.start_workflow(
                ReindexWorkflow.run,
                reindex_input(),
                id=f"workflow-{uuid4()}",
                task_queue=task_queue,
            )
            await service.batch_entered[0].wait()
            observed.append((await handle.query(ReindexWorkflow.progress)).processed)
            service.release_batch[0].set()
            await service.batch_entered[1].wait()
            observed.append((await handle.query(ReindexWorkflow.progress)).processed)
            service.release_batch[1].set()
            await service.batch_entered[2].wait()
            observed.append((await handle.query(ReindexWorkflow.progress)).processed)
            service.release_batch[2].set()
            await service.verify_entered.wait()
            observed.append((await handle.query(ReindexWorkflow.progress)).processed)
            service.release_verify.set()
            result = await handle.result()

    assert observed == [0, 10, 20, 25]
    assert observed == sorted(observed)
    assert result.status == "activated"

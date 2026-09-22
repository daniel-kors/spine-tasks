"""Deterministic Temporal workflow; all I/O is delegated to activities."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

from .models import (
    IndexBatchInput,
    MarkFailedInput,
    ProjectionInput,
    ReindexInput,
    ReindexProgress,
    ReindexResult,
    ValidateManifestsInput,
)

BATCH_SIZE = 10
ACTIVITY_TIMEOUT = timedelta(seconds=30)


def make_batch_descriptors(data: ReindexInput, workflow_id: str) -> tuple[IndexBatchInput, ...]:
    batches: list[IndexBatchInput] = []
    for batch_number, start in enumerate(range(0, len(data.manifest_paths), BATCH_SIZE)):
        activity_id = f"index-batch-{batch_number}"
        batches.append(
            IndexBatchInput(
                workspace_id=data.workspace_id,
                projection_id=data.projection_id,
                manifest_paths=data.manifest_paths[start : start + BATCH_SIZE],
                batch_number=batch_number,
                idempotency_key=f"{workflow_id}/{activity_id}/{batch_number}",
            )
        )
    return tuple(batches)


@workflow.defn
class ReindexWorkflow:
    def __init__(self) -> None:
        self.status = "pending"
        self.processed = 0
        self.total = 0
        self.cancel_requested = False

    @workflow.signal
    async def request_cancel(self) -> None:
        self.cancel_requested = True

    @workflow.query
    def progress(self) -> ReindexProgress:
        return ReindexProgress(
            status=self.status,
            processed=self.processed,
            total=self.total,
            cancel_requested=self.cancel_requested,
        )

    @workflow.run
    async def run(self, data: ReindexInput) -> ReindexResult:
        self.status = "running"
        self.total = len(data.manifest_paths)
        projection = ProjectionInput(
            workspace_id=data.workspace_id,
            projection_id=data.projection_id,
            expected_count=self.total,
        )
        try:
            await workflow.execute_activity(
                "validate_manifests",
                ValidateManifestsInput(
                    workspace_id=data.workspace_id,
                    projection_id=data.projection_id,
                    manifest_paths=data.manifest_paths,
                ),
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_attempts=3,
                    non_retryable_error_types=["ManifestValidationError"],
                ),
            )
            await workflow.execute_activity(
                "create_projection",
                projection,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            batches = make_batch_descriptors(data, workflow.info().workflow_id)
            for batch in batches:
                if self.cancel_requested:
                    return self._cancelled(data)
                count = await workflow.execute_activity(
                    "index_batch",
                    batch,
                    result_type=int,
                    activity_id=f"index-batch-{batch.batch_number}",
                    start_to_close_timeout=ACTIVITY_TIMEOUT,
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        backoff_coefficient=2,
                        maximum_interval=timedelta(seconds=5),
                        maximum_attempts=3,
                    ),
                )
                self.processed += count
            if self.cancel_requested:
                return self._cancelled(data)
            await workflow.execute_activity(
                "verify_projection",
                projection,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            if self.cancel_requested:
                return self._cancelled(data)
            await workflow.execute_activity(
                "activate_projection",
                projection,
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        except ActivityError as exc:
            await workflow.execute_activity(
                "mark_failed",
                MarkFailedInput(
                    workspace_id=data.workspace_id,
                    projection_id=data.projection_id,
                    reason_code=type(exc).__name__,
                ),
                start_to_close_timeout=ACTIVITY_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            self.status = "failed"
            return ReindexResult(
                status="failed",
                projection_id=data.projection_id,
                indexed_count=self.processed,
            )
        self.status = "activated"
        return ReindexResult(
            status="activated",
            projection_id=data.projection_id,
            indexed_count=self.processed,
        )

    def _cancelled(self, data: ReindexInput) -> ReindexResult:
        self.status = "cancelled"
        return ReindexResult(
            status="cancelled",
            projection_id=data.projection_id,
            indexed_count=self.processed,
        )

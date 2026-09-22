"""Start a synthetic reindex workflow on a local Temporal server."""

import argparse
import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from .config import TASK_QUEUE, TEMPORAL_ADDRESS
from .models import ReindexInput
from .workflow import ReindexWorkflow


async def start(workspace_id: str, projection_id: str, manifest_count: int) -> None:
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        data_converter=pydantic_data_converter,
    )
    data = ReindexInput(
        workspace_id=workspace_id,
        projection_id=projection_id,
        manifest_paths=tuple(
            f"manifests/chunk-{number:03d}.jsonl" for number in range(manifest_count)
        ),
    )
    result = await client.execute_workflow(
        ReindexWorkflow.run,
        data,
        id=f"reindex-{workspace_id}-{projection_id}",
        task_queue=TASK_QUEUE,
    )
    print(result.model_dump_json(indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a synthetic reindex workflow")
    parser.add_argument("--workspace", default="alpha")
    parser.add_argument("--projection", default="projection-demo")
    parser.add_argument("--manifest-count", type=int, default=25)
    args = parser.parse_args()
    if args.manifest_count < 1:
        parser.error("--manifest-count must be at least 1")
    asyncio.run(start(args.workspace, args.projection, args.manifest_count))


if __name__ == "__main__":
    main()

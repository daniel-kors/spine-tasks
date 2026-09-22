"""Connect to Temporal and run workflow and activity workers."""

import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from .activities import ReindexActivities
from .config import TASK_QUEUE, TEMPORAL_ADDRESS
from .service import InMemoryProjectionService
from .workflow import ReindexWorkflow


async def run_worker() -> None:
    client = await Client.connect(
        TEMPORAL_ADDRESS,
        data_converter=pydantic_data_converter,
    )
    activities = ReindexActivities(InMemoryProjectionService())
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ReindexWorkflow],
        activities=activities.registered(),
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

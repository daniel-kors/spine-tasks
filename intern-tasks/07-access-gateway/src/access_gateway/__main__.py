"""Demonstrate that the gateway removes a leaked restricted chunk."""

import asyncio
import json
from pathlib import Path

from .audit import JsonlAuditSink
from .gateway import AuthorizedRetriever
from .leaky_retriever import LeakyRetriever
from .models import RetrievedChunk, Subject
from .policy import GroupAccessPolicy


async def run() -> None:
    project_root = Path(__file__).parents[2]
    fixture = json.loads(
        (project_root / "data" / "fixtures" / "leaked-chunk.json").read_text(encoding="utf-8")
    )
    leaked = RetrievedChunk.model_validate(fixture)
    output = project_root / "build" / "security-events.jsonl"
    output.unlink(missing_ok=True)
    gateway = AuthorizedRetriever(
        LeakyRetriever((leaked,)),
        GroupAccessPolicy(),
        JsonlAuditSink(output),
    )
    result = await gateway.retrieve(
        Subject(user_id="employee-1", workspace_id="alpha", scopes={"all-employees"}),
        "Какое кодовое имя прототипа?",
    )
    print(result.model_dump_json(indent=2))
    print(f"Security event: {output}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

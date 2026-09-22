"""Run the offline demonstration from the bundled synthetic fixture."""

import asyncio
import json
from pathlib import Path

from .compose import FakeAnswerComposer
from .models import DraftAnswer, RetrievedChunk
from .service import AnswerService


async def run() -> None:
    fixture_path = Path(__file__).parents[2] / "data" / "fixtures" / "example.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    chunks = tuple(RetrievedChunk.model_validate(item) for item in fixture["chunks"])
    draft = DraftAnswer.model_validate(fixture["draft"])
    composer = FakeAnswerComposer({fixture["question"]: draft})
    result = await AnswerService(composer).answer(fixture["question"], chunks)
    print(result.model_dump_json(indent=2))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

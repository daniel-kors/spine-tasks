"""Opt-in contract check against the installed real Cognee package."""

import os
from pathlib import Path

import pytest

from cognee_retriever.cognee_client import RealCogneeClient


@pytest.mark.integration
@pytest.mark.llm
@pytest.mark.skipif(not os.getenv("LLM_API_KEY"), reason="LLM_API_KEY is not configured")
async def test_real_cognee_returns_expected_chunk(tmp_path: Path) -> None:
    client = RealCogneeClient(tmp_path)
    dataset_name = f"contract_{tmp_path.name.replace('-', '_')}"
    marker = "Суточные составляют 1200 рублей."

    await client.remember([marker], dataset_name)
    results = await client.recall("Какой размер суточных?", dataset_name)

    assert results
    assert any("1200" in json_text(result) for result in results)


def json_text(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)

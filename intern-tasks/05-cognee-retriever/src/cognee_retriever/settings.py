"""Environment-backed runtime settings; secrets are never committed."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cognee_provider: Literal["fake", "real"] = "fake"
    llm_api_key: str | None = None
    projection_database: Path = Path(".local/projections.db")
    fake_dataset_directory: Path = Path(".local/fake-cognee")
    fake_results_path: Path = Path("data/fixtures/retriever/fake-results.json")

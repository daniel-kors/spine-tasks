"""Environment configuration for the HTTP application."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qa_mode: str = "fake"
    composer_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

"""Configuration helpers for the news coverage agent."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    model: str = Field(
        "gpt-4o-mini-2024-07-18", description="Default Responses model."
    )
    max_tokens: int = Field(
        600, description="Max tokens for each summary response."
    )
    temperature: float = Field(0.3, description="Generation temperature.")


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()  # pydantic settings cache internally

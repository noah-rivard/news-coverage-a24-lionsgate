"""Configuration helpers for the news coverage agent."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    manager_model: str = Field(
        "gpt-5.1", description="Coordinator/manager model for tool orchestration."
    )
    summarizer_model: str = Field(
        "gpt-5-mini", description="Specialist summarizer/formatter model."
    )
    classifier_model: str = Field(
        "ft:gpt-4.1-2025-04-14:personal:news-categorizer:BY2DIiT5",
        description="Fine-tuned classifier that returns category paths.",
    )
    max_tokens: int = Field(
        1200,
        description=(
            "Max tokens for each summary response; raise if long articles are truncating."
        ),
    )
    temperature: float = Field(0.3, description="Generation temperature.")
    routing_confidence_floor: float = Field(
        0.5,
        description=(
            "Minimum classifier confidence to use a specialized prompt. "
            "Below this, the coordinator defaults to general_news."
        ),
    )
    ingest_data_dir: str | None = Field(
        None,
        alias="INGEST_DATA_DIR",
        description="Optional override for ingest storage root; defaults to data/ingest.",
    )


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()  # pydantic settings cache internally

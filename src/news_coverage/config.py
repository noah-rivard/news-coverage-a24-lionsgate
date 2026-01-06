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
    max_tokens: int | None = Field(
        None,
        description=(
            "Optional max tokens for each summary response. "
            "Unset or 0 means no explicit cap."
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
    final_output_path: str | None = Field(
        None,
        alias="FINAL_OUTPUT_PATH",
        description=(
            "Optional override for the appended final-output markdown file. "
            "Defaults to docs/templates/final_output.md in the repo root."
        ),
    )
    agent_trace_path: str | None = Field(
        None,
        alias="AGENT_TRACE_PATH",
        description=(
            "Optional path to append a plain-text agent trace log for manager runs. "
            "Disabled when unset."
        ),
    )
    buyers_of_interest: str | None = Field(
        None,
        alias="BUYERS_OF_INTEREST",
        description=(
            "Optional comma-separated list of buyer names to treat as in-scope when "
            "filtering extracted facts. When unset, all configured buyers are in-scope."
        ),
    )
    fact_buyer_guardrail_mode: str = Field(
        "section",
        alias="FACT_BUYER_GUARDRAIL_MODE",
        description=(
            "Controls fact filtering to keep output focused on in-scope buyers. "
            "Options: off, section, strict. "
            "section keeps facts in the classifier's primary section and filters other "
            "sections unless they mention an in-scope buyer. strict keeps only facts "
            "that mention an in-scope buyer."
        ),
    )


def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()  # pydantic settings cache internally
